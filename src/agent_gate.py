"""Agent gate: a rule check between an AI agent and the account it trades, and a ledger it cannot quietly rewrite.

An agent that can place orders asks the gate instead of the broker. The gate checks the order
against rules the account owner wrote (largest single order, largest position, largest loss in a day,
which symbols, which sides, how many orders a day), passes the ones that fit to the broker and refuses
the rest. Every request,
allowed or not, is appended to a ledger in which each line carries the hash of the line before it,
so an edit or a deleted line anywhere breaks every hash after it (``verify``). Each line also records
the account's equity, and ``scorecard`` reads those snapshots the way evidencedeflator.com reads a
wallet: weekly returns, t on the normal scale, and how much more record it would take to clear 2.

With a signed mandate (src/mandate.py, docs/gate/MANDATE.md) the rules come from a document the
owner signed with an Ethereum key instead of the config file. The mandate names the gate's own key;
the gate signs every ledger line with it, records the context each decision was made in, and copies
the mandate into the ledger, so ``audit`` can re-check every allowed order against the signed limits
from the ledger alone.

Brokers:
  sim          a paper account priced at Hyperliquid's live mid prices (public info API, no key). Crypto.
               With "prices": {"AAPL": 339.66, ...} in the config it uses those fixed prices instead.
  alpaca       Alpaca's paper trading API, keys from APCA_API_KEY_ID / APCA_API_SECRET_KEY. Run against
               a live paper account on 2026-10-21 (docs/gate/demo-2026-10-21-alpaca).
  hyperliquid  Hyperliquid perps (testnet by default). The gate's key is the account's approved API
               wallet: the owner approves it once from the main wallet, and the agent never holds a key
               that can trade. Use a fresh gate key per approval. Needs hyperliquid-python-sdk.

What the gate is not: it does not decide whether an order is a good idea, and it gives no advice.
The rules are the owner's; the gate only enforces them and keeps the record.

    python src/agent_gate.py demo                 # a scripted agent against a fresh sim account
    python src/agent_gate.py order BTC buy --usd 100 --config gate.json
    python src/agent_gate.py log | verify | audit | scorecard --config gate.json
    python src/agent_gate.py keygen .gate/gate.key        # the gate's own key
    python src/agent_gate.py mandate draft|sign|attach|show|examples|templates|scope|revoke|revoke-text|revoke-attach --config gate.json
    python src/agent_gate.py attest --config gate.json        # a signed summary of the ledger for a third party
    python src/agent_gate.py verify-attestation att.json --config gate.json
    python src/agent_gate.py panel a/gate.json b/gate.json --html panel.html   # every gate on one page
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
import mandate as mandate_mod  # noqa: E402

GENESIS = "0" * 64
DAY_S = 86400
WEEK_S = 7 * DAY_S

DEFAULTS: Dict[str, Any] = {
    "broker": "sim",
    "state_dir": ".gate",
    "starting_cash": 10000.0,
    "max_order_usd": 500.0,
    "max_position_usd": 2000.0,
    "max_daily_loss_usd": 200.0,
    "allow": ["BTC", "ETH", "SOL"],
    "max_orders_per_day": 20,
}


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
        base = os.path.dirname(os.path.abspath(path))
        for k in ("state_dir", "mandate", "gate_key"):
            if cfg.get(k) and not os.path.isabs(cfg[k]):
                cfg[k] = os.path.join(base, cfg[k])
    cfg["allow"] = [s.upper() for s in cfg.get("allow") or []]
    return cfg


# ---------------------------------------------------------------- ledger

def _canon(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(prev: str, entry: Dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k not in ("hash", "gate_sig")}
    return hashlib.sha256((prev + _canon(body)).encode()).hexdigest()


def line_message(h: str) -> str:
    """What the gate's key signs for a ledger line: its hash, which already covers the line and all before it."""
    return f"agent-gate ledger line {h}"


class Ledger:
    """Append-only JSON lines; line i stores sha256(hash of line i-1 + line i without its hash).

    With a signer, each line also carries ``gate_sig``, the gate key's signature of that hash.
    """

    def __init__(self, path: str):
        self.path = path

    def read(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, entry: Dict[str, Any], signer: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
        rows = self.read()
        prev = rows[-1]["hash"] if rows else GENESIS
        entry = dict(entry, seq=len(rows), prev=prev)
        entry["hash"] = entry_hash(prev, entry)
        if signer:
            entry["gate_sig"] = signer(line_message(entry["hash"]))
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canon(entry) + "\n")
        return entry

    def verify(self) -> Dict[str, Any]:
        return verify_chain(self.read())


def verify_chain(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """First line whose stored prev or hash does not match a recomputation, if any."""
    prev = GENESIS
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


HL_URLS = {"testnet": "https://api.hyperliquid-testnet.xyz", "mainnet": "https://api.hyperliquid.xyz"}


class HyperliquidBroker:
    """Hyperliquid perps through an API wallet ("agent wallet") that the owner approved.

    ``account`` in the config is the owner's main address; ``gate_key`` is the key file of the API
    wallet, which only the gate reads. Hyperliquid itself lets an API wallet place and cancel orders
    for the account (whether it can also withdraw is not stated in the docs; see MANDATE.md). Market orders are sent
    as IOC limits with 5% slippage (the SDK's market_open); size is rounded down to the coin's lot.
    """

    name = "hyperliquid"

    def __init__(self, cfg: Dict[str, Any]):
        try:
            from hyperliquid.exchange import Exchange
            from hyperliquid.info import Info
        except ImportError as e:  # pragma: no cover
            raise SystemExit("hyperliquid broker needs hyperliquid-python-sdk") from e
        if not (cfg.get("gate_key") and cfg.get("account")):
            raise SystemExit("hyperliquid broker needs gate_key (the approved API wallet) and account (main address)")
        self.network = cfg.get("network", "testnet")
        self.base_url = HL_URLS[self.network]
        self.owner = cfg["account"]
        wallet = mandate_mod.load_key(cfg["gate_key"])
        self.info = Info(self.base_url, skip_ws=True)
        self.ex = Exchange(wallet, self.base_url, account_address=self.owner)
        self._lots = {a["name"].upper(): a["szDecimals"] for a in self.info.meta()["universe"]}

    def price(self, symbol: str) -> float:
        p = self.info.all_mids().get(symbol.upper())
        if p is None:
            raise ValueError(f"no price for {symbol}")
        return float(p)

    def account(self) -> Dict[str, Any]:
        st = self.info.user_state(self.owner)
        pos = {p["position"]["coin"].upper(): float(p["position"]["szi"]) for p in st.get("assetPositions", [])}
        return {"cash": float(st.get("withdrawable", 0.0)), "positions": pos,
                "equity": float(st["marginSummary"]["accountValue"])}

    def position(self, symbol: str) -> float:
        return float(self.account()["positions"].get(symbol.upper(), 0.0))

    def submit(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        sym = symbol.upper()
        d = self._lots.get(sym, 4)
        sz = int(qty * 10 ** d) / 10 ** d
        if sz <= 0:
            raise ValueError(f"{qty} {sym} rounds to zero at {d} decimals")
        r = self.ex.market_open(sym, side == "buy", sz, None, 0.05) or {}
        if r.get("status") != "ok" or not isinstance(r.get("response"), dict):
            raise RuntimeError(r.get("response") or r)  # e.g. {"status": "err", "response": "<reason>"}
        st = (r["response"].get("data") or {}).get("statuses") or [{}]
        if "error" in st[0]:
            raise RuntimeError(st[0]["error"])
        f = st[0].get("filled") or st[0].get("resting") or {}
        return {"status": "filled" if "filled" in st[0] else "resting", "symbol": sym, "side": side,
                "qty": float(f.get("totalSz", sz)), "price": float(f["avgPx"]) if f.get("avgPx") else None,
                "oid": f.get("oid")}


def hl_approve_agent(owner_account, agent_address: str, name: str = "gate", network: str = "testnet") -> Any:
    """Sign and send Hyperliquid's approveAgent from the owner's main key, for an existing agent address.

    The SDK's own approve_agent always mints a fresh random key; the gate needs its existing key
    approved, so the action is built here and signed with the SDK's sign_agent. ``owner_account`` is
    an eth_account LocalAccount. Use it only with keys you are allowed to hold (a test wallet); an
    owner with a real wallet approves the address in Hyperliquid's own app instead (docs/gate/MANDATE.md).
    """
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils.signing import get_timestamp_ms, sign_agent
    base = HL_URLS[network]
    ts = get_timestamp_ms()
    action = {"type": "approveAgent", "agentAddress": agent_address, "agentName": name, "nonce": ts}
    sig = sign_agent(owner_account, action, network == "mainnet")
    return Exchange(owner_account, base)._post_action(action, sig, ts)


def make_broker(cfg: Dict[str, Any], prices: Optional[Callable[[], Dict[str, float]]] = None):
    if cfg["broker"] == "sim":
        if prices is None and cfg.get("prices"):  # fixed prices, e.g. US stocks recorded from a broker
            fixed = {k.upper(): float(v) for k, v in cfg["prices"].items()}
            prices = lambda: fixed  # noqa: E731
        return SimBroker(cfg["state_dir"], cfg["starting_cash"], prices)
    if cfg["broker"] == "alpaca":
        return AlpacaBroker()
    if cfg["broker"] == "hyperliquid":
        return HyperliquidBroker(cfg)
    raise SystemExit(f"unknown broker {cfg['broker']}")


# ---------------------------------------------------------------- rules

def check(order: Dict[str, Any], ctx: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    """Reasons to refuse the order; empty means allowed. Pure function of order, context and rules.

    ``ctx``: price, position (signed qty held now), loss_today (equity at the start of the UTC day
    minus equity now, positive when down), orders_today (allowed orders so far today).
    An order that only shrinks an existing position is never blocked by the allow-list, side,
    daily-loss or count rules: stopping a loss must stay possible after the loss limit is hit, and a
    position left over from earlier rules must stay closable after its symbol leaves the list.
    """
    reasons = []
    sym, side, qty, price = order["symbol"], order["side"], order["qty"], ctx["price"]
    notional = qty * price
    pos = ctx["position"]
    reducing = (side == "sell" and 0 < qty <= pos) or (side == "buy" and 0 < qty <= -pos)
    if cfg.get("allow") and sym not in cfg["allow"] and not reducing:
        reasons.append(f"{sym} is not on the allow list {cfg['allow']}")
    if cfg.get("sides") and side not in cfg["sides"] and not reducing:
        reasons.append(f"{side} orders are not allowed (sides {cfg['sides']})")
    if cfg.get("max_position_usd") is not None and not reducing:
        after = pos + (qty if side == "buy" else -qty)
        grows = abs(after) > abs(pos) or after * pos < 0  # bigger, or flipped to the other side
        if abs(after) * price > cfg["max_position_usd"] and grows:
            reasons.append(f"position would be ${abs(after) * price:,.2f}, above the "
                           f"${cfg['max_position_usd']:,.0f} per-symbol position limit")
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
    """The rule check plus the ledger. With ``cfg["mandate"]`` the rules are the signed mandate's scope
    (the config's own rule fields are then ignored) and every line is signed with ``cfg["gate_key"]``."""

    def __init__(self, cfg: Dict[str, Any], broker=None, clock: Callable[[], float] = time.time):
        self.cfg = cfg
        self.clock = clock
        self.ledger = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl"))
        self.key = mandate_mod.load_key(cfg["gate_key"]) if cfg.get("gate_key") else None
        self.signer = (lambda text: mandate_mod.sign_text(self.key, text)) if self.key else None
        self.mandate: Optional[Dict[str, Any]] = None
        if cfg.get("mandate"):
            if not self.key:
                raise SystemExit("a mandate names the gate's key; set gate_key in the config")
        if cfg.get("mandate") and os.path.exists(cfg["mandate"]):
            self.mandate = mandate_mod.load(cfg["mandate"])
            bad = mandate_mod.verify(self.mandate, agent=self.key.address)
            if bad:
                raise SystemExit("mandate rejected: " + "; ".join(bad))
        self.broker = broker or make_broker(cfg)

    def _append(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self.ledger.append(entry, self.signer)

    def _mandate_state(self, now: float) -> Tuple[Optional[str], List[str]]:
        """Hash of the mandate in force (recorded in the ledger on first use) and reasons it does not hold now."""
        if not self.mandate:
            if self.cfg.get("mandate"):  # a mandate is expected but not signed yet: nothing passes
                return None, [f"mandate: none signed yet ({os.path.basename(self.cfg['mandate'])} does not exist)"]
            return None, []
        h = mandate_mod.mandate_hash(self.mandate)
        rows = self.ledger.read()
        if not any(r.get("kind") == "mandate" and r.get("mandate_hash") == h for r in rows):
            self._append({"kind": "mandate", "ts": _utc(now), "ts_unix": round(now, 3),
                          "mandate_hash": h, "signed": self.mandate})
        reasons = ["mandate: " + r for r in mandate_mod.verify(self.mandate, now=now, agent=self.key.address)]
        rev_path = self.cfg["mandate"] + ".revoked"
        if os.path.exists(rev_path):
            rev = mandate_mod.load(rev_path)
            if mandate_mod.revocation_valid(rev, self.mandate):
                if not any(r.get("kind") == "revocation" and r.get("mandate_hash") == h for r in rows):
                    self._append({"kind": "revocation", "ts": _utc(now), "ts_unix": round(now, 3),
                                  "mandate_hash": h, "revocation": rev})
                reasons.append(f"mandate: revoked by the issuer at {rev['ts']}")
        return h, reasons

    def _today(self, now: float) -> Tuple[float, int, List[Dict[str, Any]]]:
        """Equity at the first ledger line of this UTC day (None if none yet) and allowed orders today."""
        start = now - now % DAY_S
        rows = [r for r in self.ledger.read() if r["ts_unix"] >= start and "equity_before" in r]
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
        mhash, mreasons = self._mandate_state(now)
        rules = self._rules()
        acct = self.broker.account()
        try:
            price = self.broker.price(sym)
        except Exception as e:  # unknown symbol: refuse and record, nothing to size it with
            reasons = mreasons + [f"no price for {sym} ({e})"]
            if rules.get("allow") and sym not in rules["allow"]:
                reasons.insert(len(mreasons), f"{sym} is not on the allow list {rules['allow']}")
            return self._append(dict({
                "kind": "order", "ts": _utc(now), "ts_unix": round(now, 3),
                "request": {"symbol": sym, "side": side, "qty": qty, "usd": usd, "price": None, "note": note},
                "decision": "block", "reasons": reasons, "equity_before": acct["equity"],
                "equity_after": acct["equity"], "rules": rules}, **({"mandate_hash": mhash} if mhash else {})))
        if qty is None:
            qty = usd / price
        eq0, n_today, _ = self._today(now)
        equity = acct["equity"]
        ctx = {"price": price, "position": float(acct["positions"].get(sym, 0.0)),
               "loss_today": max(0.0, (eq0 if eq0 is not None else equity) - equity), "orders_today": n_today}
        order = {"symbol": sym, "side": side, "qty": qty}
        reasons = mreasons + check(order, ctx, rules)
        entry: Dict[str, Any] = {"kind": "order", "ts": _utc(now), "ts_unix": round(now, 3),
                                 "request": dict(order, usd=round(qty * price, 2), price=price, note=note),
                                 "decision": "block" if reasons else "allow", "reasons": reasons,
                                 "equity_before": equity, "rules": rules, "ctx": ctx}
        if mhash:
            entry["mandate_hash"] = mhash
        if not reasons:
            try:
                entry["fill"] = self.broker.submit(sym, side, qty, price)
            except Exception as e:  # the broker refusing is recorded, not hidden
                entry["decision"], entry["reasons"] = "error", [f"broker: {e}"]
        entry["equity_after"] = self.broker.account()["equity"]
        return self._append(entry)

    def snapshot(self, note: str = "") -> Dict[str, Any]:
        now = self.clock()
        eq = self.broker.account()["equity"]
        return self._append({"kind": "snapshot", "ts": _utc(now), "ts_unix": round(now, 3),
                             "equity_before": eq, "equity_after": eq, "note": note})

    def _rules(self) -> Dict[str, Any]:
        if self.mandate:
            return mandate_mod.rules(self.mandate)
        return {k: self.cfg.get(k) for k in ("max_order_usd", "max_position_usd", "max_daily_loss_usd", "allow",
                                             "max_orders_per_day", "sides")}

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


def audit(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Everything a third party can check from the ledger file alone, with no access to the gate.

    1. The hash chain is intact (no line edited, removed or reordered).
    2. Every mandate copied into the ledger carries a valid signature from its issuer.
    3. Every line from the first mandate on is signed by the key that mandate names, so the lines
       came from the key the owner authorised and not from someone rewriting the file wholesale.
    4. Every allowed order falls inside the mandate's time window, before any revocation, and passes
       the mandate's rules when re-checked against the context recorded with it.

    It cannot show that no order bypassed the gate; for Hyperliquid, ``hl_unlogged_fills`` compares
    the ledger with the venue's own fill history for that.
    """
    chain = verify_chain(rows)
    problems: List[str] = [] if chain["ok"] else [f"hash chain broken at line {chain['broken_at']}"]
    mandates: Dict[str, Dict[str, Any]] = {}
    revoked: Dict[str, float] = {}
    n_allowed = n_checked = 0
    for r in rows:
        i, kind, mh = r.get("seq"), r.get("kind"), r.get("mandate_hash")
        if kind == "mandate":
            if mandate_mod.mandate_hash(r["signed"]) != mh:
                problems.append(f"line {i}: mandate copy does not match its hash")
            for b in mandate_mod.verify(r["signed"]):
                problems.append(f"line {i}: mandate {b}")
            mandates[mh] = r["signed"]
        if kind == "revocation" and mh in mandates:
            if mandate_mod.revocation_valid(r["revocation"], mandates[mh]):
                revoked.setdefault(mh, r["ts_unix"])
            else:
                problems.append(f"line {i}: revocation not signed by the mandate's issuer")
        if mandates:
            m = mandates.get(mh) if mh else None
            expect = (m or list(mandates.values())[-1])["mandate"]["agent"]
            sig = r.get("gate_sig")
            if not sig:
                problems.append(f"line {i}: unsigned line after a mandate was recorded")
            else:
                try:
                    who = mandate_mod.recover(line_message(r["hash"]), sig)
                except Exception:
                    who = None
                if not mandate_mod.same_addr(who, expect):
                    problems.append(f"line {i}: signed by {who}, not by the mandate's agent {expect}")
        if kind != "order" or r.get("decision") != "allow":
            continue
        n_allowed += 1
        if not mandates:
            continue
        m = mandates.get(mh)
        if m is None:
            problems.append(f"line {i}: allowed order cites no recorded mandate")
            continue
        md = m["mandate"]
        if not (mandate_mod.parse_iso(md["not_before"]) <= r["ts_unix"] < mandate_mod.parse_iso(md["expires"])):
            problems.append(f"line {i}: allowed outside the mandate's window")
        if mh in revoked and r["ts_unix"] >= revoked[mh]:
            problems.append(f"line {i}: allowed after the mandate was revoked")
        if "ctx" not in r:
            problems.append(f"line {i}: no recorded context to re-check against")
            continue
        req = r["request"]
        again = check({"symbol": req["symbol"], "side": req["side"], "qty": req["qty"]}, r["ctx"],
                      mandate_mod.rules(m))
        n_checked += 1
        if again:
            problems.append(f"line {i}: allowed, but the mandate's rules say no: " + "; ".join(again))
    return {"ok": not problems, "lines": len(rows), "chain_ok": chain["ok"], "mandates": len(mandates),
            "orders_allowed": n_allowed, "orders_rechecked": n_checked, "problems": problems}


ATTEST_HEADER = "Agent gate attestation v0 (evidencedeflator.com/gate)\n"


def attestation_statement(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What the attestation asserts about a ledger: its head, its mandates, its counts and the audit result.

    Everything here is recomputable from the ledger lines, which is how a third party checks it."""
    a = audit(rows)
    mands = []
    for r in rows:
        if r.get("kind") == "mandate":
            m = r["signed"]["mandate"]
            mands.append({"hash": r["mandate_hash"], "id": m["id"], "issuer": m["issuer"], "agent": m["agent"],
                          "venue": m["venue"], "account": m["account"], "expires": m["expires"]})
    orders = [r for r in rows if r.get("kind") == "order"]
    return {"type": "agent-gate-attestation", "version": "0",
            "ledger": {"lines": len(rows), "head": rows[-1]["hash"] if rows else GENESIS,
                       "first": rows[0]["ts"] if rows else None, "last": rows[-1]["ts"] if rows else None},
            "mandates": mands,
            "orders": {"allowed": sum(1 for r in orders if r.get("decision") == "allow"),
                       "blocked": sum(1 for r in orders if r.get("decision") == "block"),
                       "errors": sum(1 for r in orders if r.get("decision") == "error"),
                       "rechecked": a["orders_rechecked"]},
            "audit_ok": a["ok"], "problems": a["problems"]}


def attest(rows: List[Dict[str, Any]], key, now: Optional[float] = None) -> Dict[str, Any]:
    """A signed, portable summary of the ledger for a broker, an auditor or a counterparty.

    Signed with the gate's key (the key the mandate names), and bound to the ledger's head hash, so the
    holder of the ledger file can confirm every number without trusting the gate or this project."""
    st = dict(attestation_statement(rows), issued_at=_utc(now if now is not None else time.time()))
    text = ATTEST_HEADER + _canon(st)
    return {"statement": st, "sig": {"scheme": "eip191", "signer": key.address,
                                     "signature": mandate_mod.sign_text(key, text)}}


def verify_attestation(att: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check an attestation against the ledger it describes (the ledger may have grown since)."""
    st, sig = att["statement"], att["sig"]
    problems: List[str] = []
    try:
        who = mandate_mod.recover(ATTEST_HEADER + _canon(st), sig["signature"])
    except Exception:
        who = None
    if not mandate_mod.same_addr(who, sig.get("signer")):
        problems.append(f"signature recovers to {who}, not the stated signer {sig.get('signer')}")
    agents = {m["agent"].lower() for m in st.get("mandates", [])}
    if agents and (who or "").lower() not in agents:
        problems.append(f"signed by {who}, which is not the gate key any recorded mandate names")
    n = st["ledger"]["lines"]
    if len(rows) < n:
        problems.append(f"the ledger has {len(rows)} lines, the attestation covers {n}")
    else:
        again = attestation_statement(rows[:n])
        for k in ("ledger", "mandates", "orders", "audit_ok", "problems"):
            if again[k] != st[k]:
                problems.append(f"{k} does not match the ledger: attested {st[k]}, recomputed {again[k]}")
    return {"ok": not problems, "signer": who, "covers_lines": n, "ledger_lines_now": len(rows),
            "problems": problems}


def panel(cfg_paths: List[str], now: Optional[float] = None) -> List[Dict[str, Any]]:
    """One row per gate (one per agent and account), read from each ledger alone: no broker call."""
    now = now if now is not None else time.time()
    day0 = now - now % DAY_S
    out = []
    for p in cfg_paths:
        cfg = load_config(p)
        rows = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl")).read()
        orders = [r for r in rows if r.get("kind") == "order"]
        today = [r for r in orders if r["ts_unix"] >= day0]
        mands = [r["signed"]["mandate"] for r in rows if r.get("kind") == "mandate"]
        revoked = any(r.get("kind") == "revocation" for r in rows)
        eq = next((r["equity_after"] for r in reversed(rows) if r.get("equity_after") is not None), None)
        a = audit(rows)
        out.append({"name": cfg.get("name") or os.path.basename(os.path.dirname(os.path.abspath(p))),
                    "broker": cfg["broker"], "config": p,
                    "rules": ("mandate " + mands[-1]["id"] + (" (revoked)" if revoked else "")) if mands
                    else "config file", "expires": mands[-1]["expires"] if mands else None,
                    "lines": len(rows), "allowed": sum(1 for r in orders if r.get("decision") == "allow"),
                    "blocked": sum(1 for r in orders if r.get("decision") == "block"),
                    "allowed_today": sum(1 for r in today if r.get("decision") == "allow"),
                    "blocked_today": sum(1 for r in today if r.get("decision") == "block"),
                    "last": rows[-1]["ts"] if rows else None, "equity": eq,
                    "audit_ok": a["ok"], "chain_ok": a["chain_ok"], "problems": len(a["problems"])})
    return out


def panel_text(rows: List[Dict[str, Any]]) -> str:
    head = f"{'gate':<28} {'broker':<12} {'rules':<26} {'allowed':>7} {'blocked':>7} {'audit':>6}  last line"
    lines = [head, "-" * len(head)]
    for r in rows:
        lines.append(f"{r['name'][:28]:<28} {r['broker']:<12} {r['rules'][:26]:<26} {r['allowed']:>7} "
                     f"{r['blocked']:>7} {('ok' if r['audit_ok'] else 'FAIL'):>6}  {r['last'] or '-'}")
    return "\n".join(lines)


def panel_html(rows: List[Dict[str, Any]], generated: str) -> str:
    def esc(s: Any) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    trs = ""
    for r in rows:
        eq = "—" if r["equity"] is None else f"${r['equity']:,.0f}"
        until = ("until " + r["expires"]) if r["expires"] else "limits from the config file"
        trs += (f"<tr><td><b>{esc(r['name'])}</b><span>{esc(r['broker'])}</span></td>"
                f"<td>{esc(r['rules'])}<span>{esc(until)}</span></td>"
                f"<td class=n>{r['allowed']}<span>{r['allowed_today']} today</span></td>"
                f"<td class=n><i>{r['blocked']}</i><span>{r['blocked_today']} today</span></td>"
                f"<td class=n>{eq}</td>"
                f"<td class={'ok' if r['audit_ok'] else 'bad'}>{'audit ok' if r['audit_ok'] else 'audit FAILS'}"
                f"<span>{r['lines']} lines · last {esc(r['last'] or '—')}</span></td></tr>")
    return f"""<!doctype html><meta charset=utf-8><title>Agent gate · panel</title>
<style>body{{margin:0;background:#F6F4EE;color:#141414;font:15px/1.5 Inter,'Segoe UI',system-ui,sans-serif;padding:40px 24px}}
main{{max-width:1080px;margin:0 auto}}h1{{font:600 30px/1.2 Newsreader,Georgia,serif;margin:0}}
p{{color:#6B6A64;margin:8px 0 26px}}table{{width:100%;border-collapse:collapse;background:#FFFDF8;border:1px solid #DCD7CB}}
th{{font:500 11px 'JetBrains Mono',Consolas,monospace;letter-spacing:.1em;text-transform:uppercase;color:#6B6A64;text-align:left;padding:12px 14px;border-bottom:1px solid #DCD7CB}}
td{{padding:14px;border-bottom:1px solid #E7E3D9;vertical-align:top}}td span{{display:block;color:#6B6A64;font-size:12.5px;margin-top:2px}}
td.n{{font:600 18px 'JetBrains Mono',Consolas,monospace}}td.n span{{font:12.5px Inter,sans-serif}}i{{font-style:normal;color:#B3261E}}
.ok{{color:#1F6B47;font-weight:600}}.bad{{color:#B3261E;font-weight:700}}</style>
<main><h1>Agent gate · every agent, every account</h1>
<p>Read from each gate's own ledger, nothing from the brokers. Generated {esc(generated)} by <code>agent-gate panel</code>.</p>
<table><tr><th>Gate</th><th>Rules</th><th>Allowed</th><th>Blocked</th><th>Equity</th><th>Ledger</th></tr>{trs}</table></main>"""


def hl_unlogged_fills(rows: List[Dict[str, Any]], owner: str, network: str = "testnet") -> Dict[str, Any]:
    """Hyperliquid fills on the owner's account since the ledger began that no ledger line accounts for.

    This is the completeness half of the audit: the venue, not the gate, says what traded. Any order
    id here was placed by some other key (the owner's own, or a second API wallet) and bypassed the gate.
    """
    from hyperliquid.info import Info
    start = int(min(r["ts_unix"] for r in rows) * 1000) if rows else 0
    fills = Info(HL_URLS[network], skip_ws=True).user_fills_by_time(owner, start)
    logged = {str((r.get("fill") or {}).get("oid")) for r in rows if (r.get("fill") or {}).get("oid") is not None}
    unlogged = sorted({str(f["oid"]) for f in fills} - logged)
    return {"venue_fills": len(fills), "logged_orders": len(logged), "unlogged_order_ids": unlogged,
            "complete": not unlogged}


# ---------------------------------------------------------------- cli

def _fmt(e: Dict[str, Any]) -> str:
    if e["kind"] == "snapshot":
        return f"#{e['seq']:<3} {e['ts']}  snapshot  equity ${e['equity_after']:,.2f}"
    if e["kind"] == "mandate":
        m = e["signed"]["mandate"]
        return (f"#{e['seq']:<3} {e['ts']}  mandate   {m['id']} from {m['issuer'][:10]}… for agent {m['agent'][:10]}…, "
                f"until {m['expires']}  {json.dumps(m['scope'], ensure_ascii=False)}")
    if e["kind"] == "revocation":
        return f"#{e['seq']:<3} {e['ts']}  REVOKED   mandate {e['revocation']['revoke']} by its issuer"
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


def mandate_cli(a: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    """draft | sign | attach | show | examples | templates | scope | revoke | revoke-text | revoke-attach,
    against the mandate path in the config."""
    sub = a.args[0] if a.args else "show"
    if sub == "templates":  # needs no mandate path
        import mandate_templates
        print(mandate_templates.render(a.account_usd))
        return
    path = cfg.get("mandate")
    if not path:
        raise SystemExit('set "mandate": "mandate.json" in the config first')
    unsigned = path + ".unsigned.json"
    if sub == "draft":
        if not (a.issuer and cfg.get("gate_key")):
            raise SystemExit("draft needs --issuer 0x… (the owner's address) and gate_key in the config")
        venue = cfg["broker"] + ("-" + cfg.get("network", "testnet") if cfg["broker"] == "hyperliquid" else "")
        scope, days = cfg, a.days
        if a.template:
            import mandate_templates
            if not a.account_usd:
                raise SystemExit("--template needs --account-usd (the account's value; limits scale with it)")
            scope = mandate_templates.scope(a.template, a.account_usd, cfg.get("allow"))
            days = a.days if a.days_given else mandate_templates.TEMPLATES[a.template]["days"]
            print(f"template {a.template}: {json.dumps(scope)} for {days:g} days "
                  "(candidate numbers; run mandate examples before signing)")
            print()
        if a.text:  # the owner's own sentence, read without a model
            import mandate_text
            r = mandate_text.parse(a.text, default_days=a.days)
            print(mandate_text.render(r))
            print()
            if [k for k in r["missing"] if k != "max_position_usd"]:
                raise SystemExit("not drafted: add what is missing to the sentence")
            scope, days = r["scope"], r["days"]
        m = mandate_mod.draft(a.issuer, mandate_mod.address_of(cfg["gate_key"]), venue,
                              cfg.get("account") or cfg["broker"], scope, days=days,
                              intent={"purpose": a.purpose, "horizon": a.horizon})
        mandate_mod.save(m, unsigned)
        print(f"wrote {unsigned}\n\nSign this exact text with the issuer's wallet (Sign message / personal_sign),"
              f" then run: mandate attach --sig 0x…\n\n{mandate_mod.message(m)}")
    elif sub in ("sign", "attach"):
        m = mandate_mod.load(unsigned)
        if sub == "sign":
            if not a.key:
                raise SystemExit("sign needs --key FILE (a local key you hold; wallet users use attach)")
            signed = mandate_mod.sign(m, a.key)
        else:
            if not a.sig:
                raise SystemExit("attach needs --sig 0x…")
            signed = mandate_mod.attach(m, a.sig)
        bad = mandate_mod.verify(signed)
        if bad:
            raise SystemExit("not saved: " + "; ".join(bad))
        mandate_mod.save(signed, path)
        print(f"wrote {path} (hash {mandate_mod.mandate_hash(signed)[:16]})")
    elif sub == "show":
        signed = mandate_mod.load(path)
        agent = mandate_mod.address_of(cfg["gate_key"]) if cfg.get("gate_key") else None
        print(json.dumps({"mandate": signed["mandate"], "hash": mandate_mod.mandate_hash(signed),
                          "problems_now": mandate_mod.verify(signed, now=time.time(), agent=agent)},
                         indent=1, ensure_ascii=False))
    elif sub == "scope":
        print(json.dumps(mandate_mod.scope_of_autonomy(mandate_mod.load(path)), indent=1, ensure_ascii=False))
    elif sub == "examples":
        import mandate_examples
        src = path if os.path.exists(path) else unsigned
        doc = mandate_mod.load(src)
        print(mandate_examples.render(mandate_examples.examples((doc.get("mandate") or doc)["scope"])))
    elif sub == "revoke-text":  # wallet issuers: print the text to sign, then revoke-attach
        d = mandate_mod.revocation_draft(mandate_mod.load(path))
        mandate_mod.save(d, path + ".revoke.unsigned.json")
        print(f"wrote {path}.revoke.unsigned.json\n\nSign this exact text with the issuer's wallet (Sign message / "
              f"personal_sign, or section 3 of evidencedeflator.com/gate/sign/), then run: "
              f"mandate revoke-attach --sig 0x…\n\n{mandate_mod.revocation_message(d['revoke'], d['ts'])}")
    elif sub == "revoke-attach":
        if not a.sig:
            raise SystemExit("revoke-attach needs --sig 0x…")
        signed = mandate_mod.load(path)
        rev = mandate_mod.attach_revocation(mandate_mod.load(path + ".revoke.unsigned.json"), a.sig)
        if not mandate_mod.revocation_valid(rev, signed):
            raise SystemExit("not saved: the signature does not recover to the mandate's issuer for this text")
        mandate_mod.save(rev, path + ".revoked")
        print(f"wrote {path}.revoked; the gate refuses every order under this mandate from now on")
    elif sub == "revoke":
        if not a.key:
            raise SystemExit("revoke needs --key FILE (the issuer's key)")
        rev = mandate_mod.revoke(mandate_mod.load(path), a.key)
        mandate_mod.save(rev, path + ".revoked")
        print(f"wrote {path}.revoked; the gate refuses every order under this mandate from now on")
    else:
        raise SystemExit(f"unknown mandate command {sub}")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Rule gate and tamper-evident ledger for an AI trading agent.")
    ap.add_argument("cmd", choices=["demo", "order", "status", "log", "verify", "audit", "scorecard", "snapshot",
                                    "init", "keygen", "mandate", "hl-approve", "attest", "verify-attestation",
                                    "panel"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--config")
    ap.add_argument("--usd", type=float)
    ap.add_argument("--qty", type=float)
    ap.add_argument("--picked-from", type=int)
    ap.add_argument("--issuer", help="mandate draft: the owner's address")
    ap.add_argument("--days", type=float, default=None, help="mandate draft: how long it lasts (default 30)")
    ap.add_argument("--purpose", help="mandate draft: what the agent is for, in your words (signed, not enforced)")
    ap.add_argument("--horizon", help="mandate draft: over what horizon, in your words (signed, not enforced)")
    ap.add_argument("--template", help="mandate draft: start from a template (mandate templates lists them)")
    ap.add_argument("--account-usd", type=float, help="mandate draft/templates: account value the template scales to")
    ap.add_argument("--key", help="mandate sign/revoke, hl-approve: a key file you hold")
    ap.add_argument("--sig", help="mandate attach / revoke-attach: the wallet's signature")
    ap.add_argument("--text", help="mandate draft: the limits in one sentence, read without a model")
    ap.add_argument("--venue", action="store_true", help="audit: also compare with the venue's fills (hyperliquid)")
    ap.add_argument("--html", help="panel: also write the panel as a web page here")
    a = ap.parse_args(argv)
    a.days_given = a.days is not None
    if a.days is None:
        a.days = 30.0
    if a.cmd == "demo":
        print(demo())
        return
    if a.cmd == "keygen":
        path = a.args[0] if a.args else os.path.join(".gate", "gate.key")
        print(f"wrote {path}\naddress {mandate_mod.keygen(path)}\nKeep this file out of git and away from the agent.")
        return
    if a.cmd == "init":
        path = a.args[0] if a.args else "gate.json"
        if os.path.exists(path):
            raise SystemExit(f"{path} exists")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2)
        print(f"wrote {path}")
        return
    if a.cmd == "panel":
        paths = a.args or ([a.config] if a.config else [])
        if not paths:
            raise SystemExit("panel needs one or more gate config files")
        rows = panel(paths)
        print(panel_text(rows))
        if a.html:
            with open(a.html, "w", encoding="utf-8") as f:
                f.write(panel_html(rows, _utc(time.time())))
            print(f"wrote {a.html}")
        return
    cfg = load_config(a.config)
    if a.cmd in ("attest", "verify-attestation"):
        led = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl"))
        if a.cmd == "attest":
            if not cfg.get("gate_key"):
                raise SystemExit("attest signs with the gate's key; set gate_key in the config")
            att = attest(led.read(), mandate_mod.load_key(cfg["gate_key"]))
            path = a.args[0] if a.args else os.path.join(cfg["state_dir"], "attestation.json")
            mandate_mod.save(att, path)
            print(f"wrote {path}")
            print(json.dumps(att["statement"], indent=1, ensure_ascii=False))
        else:
            if not a.args:
                raise SystemExit("verify-attestation needs the attestation file")
            print(json.dumps(verify_attestation(mandate_mod.load(a.args[0]), led.read()), indent=1,
                             ensure_ascii=False))
        return
    if a.cmd == "mandate":
        mandate_cli(a, cfg)
        return
    if a.cmd == "hl-approve":
        if not (a.key and cfg.get("gate_key")):
            raise SystemExit("hl-approve needs --key FILE (the owner's main key, test wallets only) and gate_key")
        owner = mandate_mod.load_key(a.key)
        r = hl_approve_agent(owner, mandate_mod.address_of(cfg["gate_key"]), "gate", cfg.get("network", "testnet"))
        print(json.dumps({"owner": owner.address, "agent": mandate_mod.address_of(cfg["gate_key"]), "response": r}))
        return
    if a.cmd in ("log", "verify", "audit", "scorecard"):
        led = Ledger(os.path.join(cfg["state_dir"], "ledger.jsonl"))
        if a.cmd == "log":
            print("\n".join(_fmt(e) for e in led.read()) or "(empty)")
        elif a.cmd == "verify":
            print(json.dumps(led.verify()))
        elif a.cmd == "audit":
            out = audit(led.read())
            if a.venue and cfg["broker"] == "hyperliquid":
                out["venue"] = hl_unlogged_fills(led.read(), cfg["account"], cfg.get("network", "testnet"))
            print(json.dumps(out, indent=1, ensure_ascii=False))
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
