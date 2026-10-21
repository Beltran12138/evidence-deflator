"""Stress-test a mandate before signing it: how bad can a day get inside these limits?

A daily-loss limit does not cap a day's loss. The gate checks it only when the agent asks to open
more risk; positions already held keep moving after the limit is hit, and nothing in v0 limits how
much exposure builds up across days. This replays the gate's own rule function (agent_gate.check)
against real Hyperliquid hourly returns, resampled in whole-day blocks (fat tails and the
co-movement between symbols kept, no normal assumption), for two agents that stay inside the rules:

  max_out  asks for the largest allowed order every hour, buying, until the gate says no. The most
           aggressive agent a mandate permits; it shows what the limits themselves allow.
  random   at the allowed pace, buys or sells a random allowed symbol at a random size. No skill.

and reports, per agent, the worst day against the daily-loss limit, the deepest drawdown, and the
exposure held at the end. With ``--position-cap`` it replays the same limits plus a per-symbol
position cap (``max_position_usd``), so a mandate can be compared with and without one before it is signed.

    python src/gate_stress.py --config gate.json [--days 30 --sims 1000 --equity 10000]

Hourly closes understate moves inside the hour; liquidation, funding and fees are not modelled.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from statistics import median
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_gate  # noqa: E402
import hl_wallet  # noqa: E402

HOUR_MS = 3_600_000


def hourly_closes(coin: str, days: int = 200, cache_dir: Optional[str] = None) -> List[List[float]]:
    """[[open_time_ms, close], …] of Hyperliquid 1h candles for the last ``days`` (at most ~5000 candles)."""
    path = os.path.join(cache_dir, f"hl-1h-{coin}.json") if cache_dir else None
    if path and os.path.exists(path) and time.time() - os.path.getmtime(path) < 86400:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    end = int(time.time() * 1000)
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1h",
                                                         "startTime": end - days * 86_400_000, "endTime": end}}).encode()
    req = urllib.request.Request(hl_wallet.INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = [[c["t"], float(c["c"])] for c in json.loads(r.read())]
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f)
    return rows


def aligned_day_blocks(series: Dict[str, List[List[float]]]) -> List[List[Dict[str, float]]]:
    """Whole UTC days of hourly returns present for every symbol: [[{sym: r}, …24 hours], …]."""
    rets: Dict[str, Dict[int, float]] = {}
    for sym, rows in series.items():
        rets[sym] = {t1: c1 / c0 - 1 for (t0, c0), (t1, c1) in zip(rows, rows[1:]) if t1 - t0 == HOUR_MS}
    common = sorted(set.intersection(*(set(r) for r in rets.values())))
    days: Dict[int, List[int]] = {}
    for t in common:
        days.setdefault(t // 86_400_000, []).append(t)
    return [[{s: rets[s][t] for s in series} for t in sorted(ts)] for _, ts in sorted(days.items()) if len(ts) == 24]


def simulate(rules: Dict[str, Any], blocks: List[List[Dict[str, float]]], agent: str, days: int, equity0: float,
             rng: random.Random) -> Dict[str, float]:
    syms = sorted(blocks[0][0])
    allow = [s for s in (rules.get("allow") or syms) if s in syms]
    price = {s: 100.0 for s in syms}
    cash, pos = equity0, {s: 0.0 for s in syms}
    peak, max_dd, worst_day, days_over = equity0, 0.0, 0.0, 0
    per_day = int(rules.get("max_orders_per_day") or 24)
    max_usd = float(rules.get("max_order_usd") or 1e12)
    for _ in range(days):
        day = rng.choice(blocks)
        eq_open = cash + sum(pos[s] * price[s] for s in syms)
        n_today, day_low = 0, eq_open
        for hour in day:
            eq = cash + sum(pos[s] * price[s] for s in syms)
            wants = agent == "max_out" or rng.random() < per_day / 24.0
            if wants and allow:
                sym = rng.choice(allow)
                side = "buy" if agent == "max_out" else rng.choice(["buy", "sell"])
                usd = max_usd if agent == "max_out" else rng.uniform(0.1, 1.0) * max_usd
                qty = usd / price[sym]
                ctx = {"price": price[sym], "position": pos[sym], "loss_today": max(0.0, eq_open - eq),
                       "orders_today": n_today}
                reasons = agent_gate.check({"symbol": sym, "side": side, "qty": qty}, ctx, rules)
                if not reasons:
                    pos[sym] += qty if side == "buy" else -qty
                    cash -= (qty if side == "buy" else -qty) * price[sym]
                    n_today += 1
            for s in syms:
                price[s] *= 1 + hour[s]
            eq = cash + sum(pos[s] * price[s] for s in syms)
            day_low = min(day_low, eq)
            peak = max(peak, eq)
            max_dd = max(max_dd, peak - eq)
        loss = eq_open - day_low
        worst_day = max(worst_day, loss)
        if rules.get("max_daily_loss_usd") and loss > float(rules["max_daily_loss_usd"]):
            days_over += 1
    exposure = sum(abs(pos[s]) * price[s] for s in syms)
    return {"worst_day_loss": worst_day, "max_drawdown": max_dd, "days_over_limit": days_over,
            "end_exposure": exposure, "end_equity": cash + sum(pos[s] * price[s] for s in syms)}


def pct(xs: List[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def stress(rules: Dict[str, Any], blocks: List[List[Dict[str, float]]], days: int = 30, sims: int = 1000,
           equity0: float = 10_000.0, seed: int = 20261021, position_cap: Optional[float] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if position_cap is not None:
        rules = dict(rules, max_position_usd=position_cap)
    for agent in ("max_out", "random"):
        rng = random.Random(seed)
        runs = [simulate(rules, blocks, agent, days, equity0, rng) for _ in range(sims)]
        w = [r["worst_day_loss"] for r in runs]
        out[agent] = {
            "worst_day_loss_p50": round(median(w), 2), "worst_day_loss_p95": round(pct(w, .95), 2),
            "worst_day_loss_p99": round(pct(w, .99), 2),
            "share_of_runs_with_a_day_over_limit": round(sum(1 for r in runs if r["days_over_limit"]) / sims, 3),
            "max_drawdown_p50": round(median(r["max_drawdown"] for r in runs), 2),
            "max_drawdown_p95": round(pct([r["max_drawdown"] for r in runs], .95), 2),
            "end_exposure_p50": round(median(r["end_exposure"] for r in runs), 2),
            "end_exposure_p95": round(pct([r["end_exposure"] for r in runs], .95), 2)}
    return out


def report(rules: Dict[str, Any], res: Dict[str, Any], cap_res: Optional[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    lim = rules.get("max_daily_loss_usd")
    L = [f"Mandate stress test: {meta['days']} days x {meta['sims']} runs, starting equity ${meta['equity']:,.0f}, "
         f"{meta['blocks']} real days of Hyperliquid hourly returns ({', '.join(meta['symbols'])}, "
         f"{meta['first_day']} to {meta['last_day']}), resampled by whole day.",
         f"Limits: largest order ${rules.get('max_order_usd'):,}, daily loss ${lim:,}, "
         f"{rules.get('max_orders_per_day')} orders a day, symbols {rules.get('allow')}, "
         f"position limit {('$%s' % format(rules['max_position_usd'], ',')) if rules.get('max_position_usd') else 'none'}.", ""]
    pc = rules.get("max_position_usd")
    for name, r in (("limits as given" + (f" (position limit ${pc:,.0f})" if pc else " (no position limit)"), res),
                    (f"what-if: the same limits with a ${meta.get('position_cap') or 0:,.0f} per-symbol position limit",
                     cap_res)):
        if not r:
            continue
        L.append(name)
        for agent, label in (("max_out", "agent that uses every limit"), ("random", "agent with no skill")):
            a = r[agent]
            L.append(f"  {label:<30} worst day p50 ${a['worst_day_loss_p50']:>9,.0f}  p95 ${a['worst_day_loss_p95']:>9,.0f}"
                     f"  p99 ${a['worst_day_loss_p99']:>9,.0f}   runs with a day over the ${lim:,} limit "
                     f"{a['share_of_runs_with_a_day_over_limit']:.0%}   drawdown p95 ${a['max_drawdown_p95']:>9,.0f}"
                     f"   exposure at end p95 ${a['end_exposure_p95']:>9,.0f}")
        L.append("")
    L.append("The daily-loss limit stops new risk, not losses on what is already held. Hourly closes; no liquidation, "
             "funding or fees.")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Stress-test a mandate's limits on real Hyperliquid returns.")
    ap.add_argument("--config")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--sims", type=int, default=1000)
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--position-cap", type=float, help="also replay the limits with max_position_usd set to this")
    ap.add_argument("--json", help="write the numbers here")
    a = ap.parse_args(argv)
    cfg = agent_gate.load_config(a.config)
    if cfg.get("mandate"):
        import mandate as mandate_mod
        rules = mandate_mod.rules(mandate_mod.load(cfg["mandate"]))
    else:
        rules = {k: cfg.get(k) for k in ("max_order_usd", "max_position_usd", "max_daily_loss_usd", "allow",
                                          "max_orders_per_day")}
    syms = [s for s in rules.get("allow") or ["BTC", "ETH"]]
    cache = os.path.join(cfg["state_dir"], "stress-cache")
    series = {s: hourly_closes(s, cache_dir=cache) for s in syms}
    blocks = aligned_day_blocks(series)
    first = time.strftime("%Y-%m-%d", time.gmtime(min(r[0] for r in series[syms[0]]) / 1000))
    last = time.strftime("%Y-%m-%d", time.gmtime(max(r[0] for r in series[syms[0]]) / 1000))
    res = stress(rules, blocks, a.days, a.sims, a.equity)
    cap = stress(rules, blocks, a.days, a.sims, a.equity, position_cap=a.position_cap) if a.position_cap else None
    meta = {"days": a.days, "sims": a.sims, "equity": a.equity, "blocks": len(blocks), "symbols": syms,
            "first_day": first, "last_day": last, "position_cap": a.position_cap, "seed": 20261021}
    print(report(rules, res, cap, meta))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "rules": rules, "as_given": res, "with_position_cap": cap}, f, indent=1)


if __name__ == "__main__":
    main()
