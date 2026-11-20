"""Part 1 of docs/data/hl/ALERT_LIST_PREREG.md: how many leaderboard wallets clear bar(N) today.

    python tools/alert_list_count.py            # the 1,500 shrink-test wallets, cached portfolios
    python tools/alert_list_count.py --extra    # add the 5,000 second draw (fetches; slow)

Writes docs/data/hl/alert-list/count-<date>.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import hl_wallet  # noqa: E402
from build_hl_board import fetch_portfolio  # noqa: E402
from shrink_test import CACHE, sample_addresses  # noqa: E402

OUT = os.path.join(ROOT, "docs", "data", "hl", "alert-list")
EXTRA_SEED, EXTRA_N = 20261119, 5000
LINE = 15


def beta_ppf(p, a, b):
    """Inverse of the regularized incomplete beta, by bisection (enough for Clopper-Pearson)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _cf(a, b, x) / a
    return 1 - math.exp(lbt) * _cf(b, a, 1 - x) / b


def _cf(a, b, x):  # Lentz continued fraction (Numerical Recipes betacf)
    tiny = 1e-300
    c, d = 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((a + m2 - 1) * (a + m2)), -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
    return h


def clopper_pearson(k, n, level=0.95):
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else beta_ppf(a, k, n - k + 1)
    hi = 1.0 if k == n else beta_ppf(1 - a, k + 1, n - k)
    return lo, hi


def score_all(addrs):
    rows = []
    for a in addrs:
        try:
            pf = fetch_portfolio(CACHE, a, False)
            rets, _, _, _ = hl_wallet.weekly_returns(pf)
            sc = hl_wallet.score(rets)
        except Exception:
            sc = {"t": None}
        rows.append({"address": a, "t": sc.get("t"), "weeks": sc.get("weeks")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", action="store_true")
    ap.add_argument("--n-board", type=int, required=True, help="accounts on the board on the run day")
    args = ap.parse_args()
    n_board, first = sample_addresses(False)
    addrs = list(first)
    if args.extra:
        from shrink_test import fetch_leaderboard
        rest = sorted({r["ethAddress"].lower() for r in fetch_leaderboard(CACHE, False)} - set(first))
        addrs += random.Random(EXTRA_SEED).sample(rest, min(EXTRA_N, len(rest)))
    bar = hl_wallet.bar(args.n_board)
    rows = score_all(addrs)
    scored = [r for r in rows if r["t"] is not None]
    k = sum(1 for r in scored if r["t"] >= bar)
    n = len(rows)
    lo, hi = clopper_pearson(k, n)
    est, est_lo, est_hi = k / n * args.n_board, lo * args.n_board, hi * args.n_board
    decision = ("no list at this bar" if est_hi < LINE else "a list exists" if est >= LINE
                else "not enough sample")
    out = {"run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "prereg": "ALERT_LIST_PREREG.md",
           "n_board": args.n_board, "bar": round(bar, 3), "sampled": n, "scored": len(scored),
           "alertable": k, "t_ge_2": sum(1 for r in scored if r["t"] >= 2),
           "top_t": sorted((r["t"] for r in scored), reverse=True)[:10],
           "estimate": round(est, 1), "interval95": [round(est_lo, 1), round(est_hi, 1)], "line": LINE,
           "decision": decision, "alertable_wallets": [r for r in scored if r["t"] >= bar]}
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "count-" + out["run"][:10] + ("-extra" if args.extra else "") + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "alertable_wallets"}, indent=1))


if __name__ == "__main__":
    main()
