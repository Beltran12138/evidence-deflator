"""Agent gate: a rule check between an AI agent and the account it trades, and a ledger it cannot quietly rewrite.

An agent that can place orders asks the gate instead of the broker. The gate checks the order
against rules the account owner wrote (largest single order, largest loss in a day, which symbols,
how many orders a day), passes the ones that fit to the broker and refuses the rest. Every request,
allowed or not, is appended to a ledger in which each line carries the hash of the line before it,
so an edit or a deleted line anywhere breaks every hash after it (``verify``). Each line also records
the account's equity, and ``scorecard`` reads those snapshots the way evidencedeflator.com reads a
wallet: weekly returns, t on the normal scale, and how much more record it would take to clear 2.

Brokers:
  sim     a paper account priced at Hyperliquid's live mid prices (public info API, no key). Crypto.
  alpaca  Alpaca's paper trading API, keys from APCA_API_KEY_ID / APCA_API_SECRET_KEY. Run against
          a live paper account on 2026-10-21 (docs/gate/demo-2026-10-21-alpaca).

What the gate is not: it does not decide whether an order is a good idea, and it gives no advice.
The rules are the owner's; the gate only enforces them and keeps the record.

    python src/agent_gate.py demo                 # a scripted agent against a fresh sim account
    python src/agent_gate.py order BTC buy --usd 100 --config gate.json
    python src/agent_gate.py log | verify | scorecard --config gate.json
    python src/gate_server.py --config gate.json  # the same gate as an MCP server for an agent
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hl_wallet  # noqa: E402

GENESIS = "0" * 64
DAY_S = 86400
WEEK_S = 7 * DAY_S

DEFAULTS: Dict[str, Any] = {
    "broker": "sim",
    "state_dir": ".gate",
    "starting_cash": 10000.0,
    "max_order_usd": 500.0,
    "max_daily_loss_usd": 200.0,
    "allow": ["BTC", "ETH", "SOL"],
    "max_orders_per_day": 20,
}


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
        if not os.path.isabs(cfg["state_dir"]):
            cfg["state_dir"] = os.path.join(os.path.dirname(os.path.abspath(path)), cfg["state_dir"])
    cfg["allow"] = [s.upper() for s in cfg.get("allow") or []]
    return cfg


# ---------------------------------------------------------------- ledger

def _canon(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(prev: str, entry: Dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((prev + _canon(body)).encode()).hexdigest()


class Ledger:
    """Append-only JSON lines; line i stores sha256(hash of line i-1 + line i without its hash)."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.read()
        prev = rows[-1]["hash"] if rows else GENESIS
        entry = dict(entry, seq=len(rows), prev=prev)
        entry["hash"] = entry_hash(prev, entry)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canon(entry) + "\n")
        return entry

    def verify(self) -> Dict[str, Any]:
        """First line whose stored prev or hash does not match a recomputation, if any."""
        prev = GENESIS
        rows = self.read()
        for i, row in enumerate(rows):
            if row.get("seq") != i or row.get("prev") != prev or row.get("hash") != entry_hash(prev, row):
                return {"ok": False, "lines": len(rows), "broken_at": i}
            prev = row["hash"]
        return {"ok": True, "lines": len(rows), "head": prev}


# ---------------------------------------------------------------- brokers

def hyperliquid_mids(timeout: float = 15.0) -> Dict[str, float]:
    body = json.dumps({"type": "allMids"}).encode()
    req = urllib.request.Request(hl_wallet.INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return {k.upper(): float(v) for k, v in json.loads(r.read()).items() if not k.startswith("@")}


class SimBroker:
    """Paper account filled at the current mid. State is a JSON file next to the ledger."""

    name = "sim"

    def __init__(self, state_dir: str, starting_cash: float,
                 prices: Optional[Callable[[], Dict[str, float]]] = None):
        self.path = os.path.join(state_dir, "sim.json")
        self.starting_cash = float(starting_cash)
        self._prices = prices or hyperliquid_mids
        self._cache: Optional[Tuple[float, Dict[str, float]]] = None

    def prices(self) -> Dict[str, float]:
        if self._cache and time.time() - self._cache[0] < 5:
            return self._cache[1]
        p = self._prices()
        self._cache = (time.time(), p)
        return p

    def _state(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {"cash": self.starting_cash, "positions": {}}

    def _save(self, s: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)

    def price(self, symbol: str) -> float:
        p = self.prices().get(symbol.upper())
        if p is None:
            raise ValueError(f"no price for {symbol}")
        return p

    def account(self) -> Dict[str, Any]:
        s = self._state()
        px = self.prices() if s["positions"] else {}
        value = sum(q * px[sym] for sym, q in s["positions"].items() if sym in px)
        return {"cash": round(s["cash"], 2), "positions": s["positions"], "equity": round(s["cash"] + value, 2)}

    def position(self, symbol: str) -> float:
        return float(self._state()["positions"].get(symbol.upper(), 0.0))

    def submit(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        s = self._state()
        sym = symbol.upper()
        signed = qty if side == "buy" else -qty
        s["cash"] -= signed * price
        q = s["positions"].get(sym, 0.0) + signed
        if abs(q) < 1e-12:
            s["positions"].pop(sym, None)
        else:
            s["positions"][sym] = q
        self._save(s)
        return {"status": "filled", "symbol": sym, "side": side, "qty": qty, "price": price}


class AlpacaBroker:
    """Alpaca paper trading (v2 REST). Market orders, day; a pre-market order comes back "accepted" and fills at the open."""

    name = "alpaca"
    TRADE = "https://paper-api.alpaca.markets/v2"
    DATA = "https://data.alpaca.markets/v2"

    def __init__(self):
        self.key = os.environ.get("APCA_API_KEY_ID")
        self.secret = os.environ.get("APCA_API_SECRET_KEY")
        if not (self.key and self.secret):
            raise SystemExit("alpaca broker needs APCA_API_KEY_ID and APCA_API_SECRET_KEY")

    def _req(self, url: str, method: str = "GET", body: Optional[Dict[str, Any]] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())

    def price(self, symbol: str) -> float:
        return float(self._req(f"{self.DATA}/stocks/{symbol.upper()}/trades/latest")["trade"]["p"])

    def account(self) -> Dict[str, Any]:
        a = self._req(f"{self.TRADE}/account")
        pos = {p["symbol"]: float(p["qty"]) for p in self._req(f"{self.TRADE}/positions")}
        return {"cash": float(a["cash"]), "positions": pos, "equity": float(a["equity"])}

    def position(self, symbol: str) -> float:
        return float(self.account()["positions"].get(symbol.upper(), 0.0))

    def submit(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        o = self._req(f"{self.TRADE}/orders", "POST", {"symbol": symbol.upper(), "qty": str(qty), "side": side,
                                                     "type": "market", "time_in_force": "day"})
        return {"status": o.get("status"), "id": o.get("id"), "symbol": symbol.upper(), "side": side, "qty": qty}


def make_broker(cfg: Dict[str, Any], prices: Optional[Callable[[], Dict[str, float]]] = None):
    if cfg["broker"] == "sim":
        return SimBroker(cfg["state_dir"], cfg["starting_cash"], prices)
    if cfg["broker"] == "alpaca":
        return AlpacaBroker()
    raise SystemExit(f"unknown broker {cfg['broker']}")


# ---------------------------------------------------------------- rules

def check(order: Dict[str, Any], ctx: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    """Reasons to refuse the order; empty means allowed. Pure function of order, context and rules.

    ``ctx``: price, position (signed qty held now), loss_today (equity at the start of the UTC day
    minus equity now, positive when down), orders_today (allowed orders so far today).
    An order that only shrinks an existing position is never blocked by the daily-loss or count
    rules: stopping a loss must stay possible after the loss limit is hit.
    """
    reasons = []
    sym, side, qty, price = order["symbol"], order["side"], order["qty"], ctx["price"]
    notional = qty * price
    pos = ctx["position"]
    reducing = (side == "sell" and 0 < qty <= pos) or (side == "buy" and 0 < qty <= -pos)
    if cfg.get("allow") and sym not in cfg["allow"]:
        reasons.append(f"{sym} is not on the allow list {cfg['allow']}")
    if cfg.get("max_order_usd") is not None and notional > cfg["max_order_usd"]:
        reasons.append(f"order is ${notional:,.2f}, above the ${cfg['max_order_usd']:,.0f} single-order limit")
    if not reducing:
        if cfg.get("max_daily_loss_usd") is not None and ctx["loss_today"] >= cfg["max_daily_loss_usd"]:
            reasons.append(f"down ${ctx['loss_today']:,.2f} today, at or past the "
                           f"${cfg['max_daily_loss_usd']:,.0f} daily-loss limit (only reducing orders pass)")
        if cfg.get("max_orders_per_day") is not None and ctx["orders_today"] >= cfg["max_orders_per_day"]:
            reasons.append(f"{ctx['orders_today']} orders today, the limit is {cfg['max_orders_per_day']}")
    return reasons


# ---------------------------------------------------------------- gate

def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Gate:
    def __init__(self, cfg: Dict[str, Any], broker=None, clock: Callable[[], float] = time.time):
        self.cfg = cfg
        self.broker = broker or make_broker(cfg)
        self.ledger = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl"))
        self.clock = clock

    def _today(self, now: float) -> Tuple[float, int, List[Dict[str, Any]]]:
        """Equity at the first ledger line of this UTC day (None if none yet) and allowed orders today."""
        start = now - now % DAY_S
        rows = [r for r in self.ledger.read() if r["ts_unix"] >= start]
        eq0 = rows[0]["equity_before"] if rows else None
        n = sum(1 for r in rows if r.get("kind") == "order" and r.get("decision") == "allow")
        return eq0, n, rows

    def place(self, symbol: str, side: str, usd: Optional[float] = None, qty: Optional[float] = None,
              note: str = "") -> Dict[str, Any]:
        now = self.clock()
        sym, side = symbol.upper(), side.lower()
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        if (usd is None) == (qty is None):
            raise ValueError("give exactly one of usd or qty")
        acct = self.broker.account()
        try:
            price = self.broker.price(sym)
        except Exception as e:  # unknown symbol: refuse and record, nothing to size it with
            reasons = [f"no price for {sym} ({e})"]
            if self.cfg.get("allow") and sym not in self.cfg["allow"]:
                reasons.insert(0, f"{sym} is not on the allow list {self.cfg['allow']}")
            return self.ledger.append({
                "kind": "order", "ts": _utc(now), "ts_unix": round(now, 3),
                "request": {"symbol": sym, "side": side, "qty": qty, "usd": usd, "price": None, "note": note},
                "decision": "block", "reasons": reasons, "equity_before": acct["equity"],
                "equity_after": acct["equity"], "rules": self._rules()})
        if qty is None:
            qty = usd / price
        eq0, n_today, _ = self._today(now)
        equity = acct["equity"]
        ctx = {"price": price, "position": float(acct["positions"].get(sym, 0.0)),
               "loss_today": max(0.0, (eq0 if eq0 is not None else equity) - equity), "orders_today": n_today}
        order = {"symbol": sym, "side": side, "qty": qty}
        reasons = check(order, ctx, self.cfg)
        entry: Dict[str, Any] = {"kind": "order", "ts": _utc(now), "ts_unix": round(now, 3),
                                 "request": dict(order, usd=round(qty * price, 2), price=price, note=note),
                                 "decision": "block" if reasons else "allow", "reasons": reasons,
                                 "equity_before": equity, "rules": self._rules()}
        if not reasons:
            try:
                entry["fill"] = self.broker.submit(sym, side, qty, price)
            except Exception as e:  # the broker refusing is recorded, not hidden
                entry["decision"], entry["reasons"] = "error", [f"broker: {e}"]
        entry["equity_after"] = self.broker.account()["equity"]
        return self.ledger.append(entry)

    def snapshot(self, note: str = "") -> Dict[str, Any]:
        now = self.clock()
        eq = self.broker.account()["equity"]
        return self.ledger.append({"kind": "snapshot", "ts": _utc(now), "ts_unix": round(now, 3),
                                   "equity_before": eq, "equity_after": eq, "note": note})

    def _rules(self) -> Dict[str, Any]:
        return {k: self.cfg.get(k) for k in ("max_order_usd", "max_daily_loss_usd", "allow", "max_orders_per_day")}

    def scorecard(self, picked_from: Optional[int] = None) -> Dict[str, Any]:
        return scorecard(self.ledger.read(), picked_from)


def scorecard(rows: List[Dict[str, Any]], picked_from: Optional[int] = None) -> Dict[str, Any]:
    """The account's own record, read from the ledger's equity snapshots.

    Weekly grid anchored at the last line, the equity at the last line on or before each node,
    weekly return = change / equity at the start. Scored with hl_wallet.score and hl_wallet.verdict,
    so the bars are the site's: 2 for one agent judged on its own, best-of-N if it was picked from
    several (``picked_from``). Under 8 weeks there is no verdict, only how long it has run.
    The comparison is with doing nothing (cash), not with a market index.
    """
    pts = [(r["ts_unix"], r["equity_after"]) for r in rows if r.get("equity_after")]
    out: Dict[str, Any] = {"lines": len(rows), "allowed": sum(1 for r in rows if r.get("decision") == "allow"),
                           "blocked": sum(1 for r in rows if r.get("decision") == "block")}
    if len(pts) < 2:
        return dict(out, weeks=0, verdict="too_short", note="no equity history yet")
    start, end = pts[0][0], pts[-1][0]
    grid = list(range(int(end), int(start) - 1, -WEEK_S))[::-1]
    nodes, i = [], 0
    for g in grid:
        while i + 1 < len(pts) and pts[i + 1][0] <= g:
            i += 1
        if pts[i][0] <= g and (not nodes or nodes[-1] != i):
            nodes.append(i)
    rets = [((pts[b][1] - pts[a][1]) / pts[a][1], 1.0) for a, b in zip(nodes, nodes[1:]) if pts[a][1] > 0]
    sc = hl_wallet.score(rets)
    v = hl_wallet.verdict(sc, picked_from)
    days = (end - start) / DAY_S
    out.update(days=round(days, 1), weeks=sc.get("weeks", 0), sharpe=sc.get("sharpe"), t=sc.get("t"),
               verdict=v["key"], bar=v["bar"], equity_first=pts[0][1], equity_last=pts[-1][1])
    if sc.get("sharpe") and sc["sharpe"] > 0:
        need = hl_wallet.months_to_clear(v["bar"], sc["sharpe"])
        out["months_to_clear_at_this_sharpe"] = round(need, 1)
    if v["key"] == "too_short":
        out["note"] = (f"{days:.0f} days of record; a verdict needs at least {hl_wallet.MIN_WEEKS} weekly intervals. "
                       "Until then this is a log, not evidence.")
    return out


# ---------------------------------------------------------------- cli

def _fmt(e: Dict[str, Any]) -> str:
    if e["kind"] == "snapshot":
        return f"#{e['seq']:<3} {e['ts']}  snapshot  equity ${e['equity_after']:,.2f}"
    r = e["request"]
    head = f"#{e['seq']:<3} {e['ts']}  {r['side'].upper():4} {r['symbol']:<5} ${(r.get('usd') or 0):>9,.2f}"
    mark = {"allow": "ALLOWED", "block": "BLOCKED", "error": "ERROR"}[e["decision"]]
    tail = "" if e["decision"] == "allow" else "  <- " + "; ".join(e["reasons"])
    return f"{head}  {mark}{tail}"


def demo(prices: Optional[Callable[[], Dict[str, float]]] = None) -> str:
    """A scripted agent against a fresh sim account with the default rules. Live prices unless given."""
    d = tempfile.mkdtemp(prefix="gate-demo-")
    cfg = dict(DEFAULTS, state_dir=d)
    g = Gate(cfg, SimBroker(d, cfg["starting_cash"], prices))
    lines = ["rules: " + json.dumps(g._rules(), ensure_ascii=False)]
    for sym, side, usd, note in [("BTC", "buy", 300, "agent: small BTC buy"),
                                 ("ETH", "buy", 5000, "agent: all-in ETH"),
                                 ("DOGE", "buy", 100, "agent: off-list coin"),
                                 ("BTC", "sell", 150, "agent: trim BTC")]:
        lines.append(_fmt(g.place(sym, side, usd=usd, note=note)))
    v = g.ledger.verify()
    lines.append(f"ledger: {v['lines']} lines, chain ok = {v['ok']}, head {v['head'][:16]}")
    with open(g.ledger.path, encoding="utf-8") as f:
        raw = f.readlines()
    raw[1] = raw[1].replace('"decision":"block"', '"decision":"allow"')
    with open(g.ledger.path, "w", encoding="utf-8") as f:
        f.writelines(raw)
    v2 = g.ledger.verify()
    lines.append(f"after editing line #1 by hand: chain ok = {v2['ok']}, broken at line #{v2['broken_at']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Rule gate and tamper-evident ledger for an AI trading agent.")
    ap.add_argument("cmd", choices=["demo", "order", "status", "log", "verify", "scorecard", "snapshot", "init"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--config")
    ap.add_argument("--usd", type=float)
    ap.add_argument("--qty", type=float)
    ap.add_argument("--picked-from", type=int)
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        print(demo())
        return
    if a.cmd == "init":
        path = a.args[0] if a.args else "gate.json"
        if os.path.exists(path):
            raise SystemExit(f"{path} exists")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2)
        print(f"wrote {path}")
        return
    cfg = load_config(a.config)
    if a.cmd in ("log", "verify", "scorecard"):
        led = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl"))
        if a.cmd == "log":
            print("\n".join(_fmt(e) for e in led.read()) or "(empty)")
        elif a.cmd == "verify":
            print(json.dumps(led.verify()))
        else:
            print(json.dumps(scorecard(led.read(), a.picked_from), indent=1))
        return
    g = Gate(cfg)
    if a.cmd == "order":
        sym, side = a.args[0], a.args[1]
        print(_fmt(g.place(sym, side, usd=a.usd, qty=a.qty)))
    elif a.cmd == "snapshot":
        print(_fmt(g.snapshot()))
    else:
        print(json.dumps({"rules": g._rules(), "account": g.broker.account()}, indent=1))


if __name__ == "__main__":
    main()
