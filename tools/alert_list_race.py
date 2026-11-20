"""Part 2 of docs/data/hl/ALERT_LIST_PREREG.md, read on 2026-12-09: which pre-freeze signal
(t, shrunk estimate, share of winning weeks, all-time PnL) best predicts the forward record.

    python tools/alert_list_race.py            # after `shrink_test.py read` has refreshed the cache
    python tools/alert_list_race.py --refresh  # fetch every cohort portfolio again

Writes docs/data/hl/alert-list/race-<date>.json. Committed 2026-11-20, before any forward score.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import hl_wallet  # noqa: E402
from shrink_test import COHORT, OUT as SHRINK, get, score_after, spearman, until  # noqa: E402

OUT = os.path.join(ROOT, "docs", "data", "hl", "alert-list")
BOOT_SEED, BOOT_N = 20261209, 10000


def hit_before(pf, cut):
    rets, _, _, _ = hl_wallet.weekly_returns(until(pf, cut))
    return sum(1 for r, _ in rets if r > 0) / len(rets) if len(rets) >= hl_wallet.MIN_WEEKS else None


def pnl_at(pf, cut):
    pts = [p for p in until(pf, cut)["allTime"]["pnlHistory"]]
    return float(pts[-1][1]) if pts else None


def fwd_return(pf, cut):
    rets, _, _, _ = hl_wallet.weekly_returns(pf, since=cut)
    return sum(r for r, _ in rets) if len(rets) >= hl_wallet.MIN_WEEKS else None


def interval(rows, stat):
    rnd = random.Random(BOOT_SEED)
    n = len(rows)
    vals = sorted(stat([rows[rnd.randrange(n)] for _ in range(n)]) for _ in range(BOOT_N))
    return [round(vals[int(0.025 * BOOT_N)], 4), round(vals[int(0.975 * BOOT_N) - 1], 4)]


def rho(rs, k, y="z_after"):
    return spearman([r[k] for r in rs], [r[y] for r in rs])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    cut = json.load(open(COHORT, encoding="utf-8"))["frozen_at_ms"]
    est = json.load(open(os.path.join(SHRINK, "estimates.json"), encoding="utf-8"))["members"]
    rows, left_out = [], 0
    for e in est:
        pf = get(e["address"], args.refresh) if e.get("z") is not None else None
        if pf is None:
            left_out += 1
            continue
        za, _ = score_after(pf, cut)
        r = {"address": e["address"], "t": e["z"], "shrunk": e["mean"], "hit": hit_before(pf, cut),
             "pnl_rank": pnl_at(pf, cut), "z_after": za, "ret_after": fwd_return(pf, cut)}
        if None in r.values():
            left_out += 1
            continue
        rows.append(r)
    res = {"read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "prereg": "ALERT_LIST_PREREG.md",
           "n": len(rows), "left_out": left_out}
    if len(rows) < 30:
        res["decision"] = "not enough data: reading moves to 2027-01-06 under the same rules"
    else:
        d = {}
        for k in ("hit", "shrunk"):
            stat = (lambda kk: lambda rs: rho(rs, kk) - rho(rs, "t"))(k)
            d[k] = {"delta": round(stat(rows), 4), "interval95": interval(rows, stat)}
        winners = [k for k in d if d[k]["interval95"][0] > 0]
        dropped = [k for k in d if d[k]["interval95"][1] < 0]
        if winners:
            best = max(winners, key=lambda k: d[k]["delta"])
            dec = "t does not rank lists; rank by " + best
        else:
            dec = "no ranking claim on any of these signals"
        res.update({"delta_vs_t": d, "dropped": dropped, "decision": dec,
                    "rho_z_after": {k: round(rho(rows, k), 4) for k in ("t", "shrunk", "hit", "pnl_rank")},
                    "rho_ret_after": {k: round(rho(rows, k, "ret_after"), 4) for k in ("t", "shrunk", "hit", "pnl_rank")},
                    "two_by_two": {f"hit>=0.6:{a}|t>=2:{b}": statistics.fmean(
                        [r["z_after"] for r in rows if (r["hit"] >= 0.6) == a and (r["t"] >= 2) == b] or [float("nan")])
                        for a in (True, False) for b in (True, False)},
                    "two_by_two_n": {f"hit>=0.6:{a}|t>=2:{b}": sum(1 for r in rows if (r["hit"] >= 0.6) == a and (r["t"] >= 2) == b)
                                     for a in (True, False) for b in (True, False)}})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "race-" + res["read"][:10] + ".json"), "w", encoding="utf-8") as f:
        json.dump({**res, "rows": rows}, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
