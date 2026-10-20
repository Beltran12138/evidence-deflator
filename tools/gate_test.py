"""Inside platform-style gates, does our score still separate later winners from losers?

Usage:
    python tools/gate_test.py --snapshots DIR --cache DIR [--out FILE]

Pre-registered in docs/data/hl/gates/PREREG.md before any of this was computed. Same archived
boards, cohort rule and cached portfolios as tools/retro_freeze.py.
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hl_wallet import WEEK_MS, bar, score, weekly_returns  # noqa: E402
from retro_freeze import fetch_portfolio, pick, truncate  # noqa: E402

DAY_MS = 24 * 3600 * 1000
SEED = 20261020
BAR200 = bar(200)


def summed_path(rets):
    """Total summed return and the deepest fall below its running peak, on the summed path."""
    w = peak = deepest = 0.0
    for r in rets:
        w += r
        peak = max(peak, w)
        deepest = max(deepest, peak - w)
    return w, deepest


def gates(pf_before, freeze_ms):
    av = pf_before["allTime"]["accountValueHistory"]
    days = (freeze_ms - av[0][0]) / DAY_MS if av else 0
    iv, *_ = weekly_returns(pf_before, with_times=True)
    rets = [r for r, _, _, _ in iv]
    tot, dd = summed_path(rets)
    g1 = days >= 30 and tot > 0 and dd <= 0.35
    last = [r for r, _, ta, _ in iv if ta >= freeze_ms - 52 * WEEK_MS]
    tot52, dd52 = summed_path(last)
    g2 = days > 8 * 30.44 and tot52 > 0.20 and (dd52 == 0 or tot52 / dd52 > 2.5)
    return {"days_before": round(days, 1), "ret_before": round(tot, 4), "dd_before": round(dd, 4),
            "ret52": round(tot52, 4), "dd52": round(dd52, 4), "g1": g1, "g2": g2}


def med_diff_ci(rows, key, split, reps=10000, seed=SEED):
    """Median of key in the split group minus the rest, with a 95% interval resampling wallets."""
    def diff(rs):
        a = [r[key] for r in rs if split(r)]
        b = [r[key] for r in rs if not split(r)]
        return statistics.median(a) - statistics.median(b) if a and b else None
    by = {}
    for r in rows:
        by.setdefault(r["address"], []).append(r)
    addrs = list(by)
    rnd = random.Random(seed)
    vals = []
    for _ in range(reps):
        rs = [x for _ in addrs for x in by[addrs[rnd.randrange(len(addrs))]]]
        d = diff(rs)
        if d is not None:
            vals.append(d)
    vals.sort()
    point = diff(rows)
    ci = (round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals))], 3)) if vals else None
    return None if point is None else round(point, 3), ci


def share_diff_ci(rows, key, split, reps=10000, seed=SEED):
    """Share of key true in the split group minus the rest, wallet-resampled 95% interval."""
    def diff(rs):
        a = [r[key] for r in rs if split(r)]
        b = [r[key] for r in rs if not split(r)]
        return sum(a) / len(a) - sum(b) / len(b) if a and b else None
    by = {}
    for r in rows:
        by.setdefault(r["address"], []).append(r)
    addrs = list(by)
    rnd = random.Random(seed)
    vals = []
    for _ in range(reps):
        rs = [x for _ in addrs for x in by[addrs[rnd.randrange(len(addrs))]]]
        d = diff(rs)
        if d is not None:
            vals.append(d)
    vals.sort()
    point = diff(rows)
    ci = (round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals))], 3)) if vals else None
    return None if point is None else round(point, 3), ci


def group_stats(rows):
    if not rows:
        return {"n": 0}
    return {"n": len(rows), "wallets": len({r["address"] for r in rows}),
            "median_t_after": round(statistics.median(r["t_after"] for r in rows), 3),
            "blowup_share": round(sum(r["blowup"] for r in rows) / len(rows), 3),
            "median_ret_after": round(statistics.median(r["ret_after"] for r in rows), 4)}


def compare(rows, split, label):
    yes = [r for r in rows if split(r)]
    no = [r for r in rows if not split(r)]
    return {"split": label, "yes": group_stats(yes), "no": group_stats(no),
            "t_after_median_diff": med_diff_ci(rows, "t_after", split),
            "blowup_share_diff": share_diff_ci(rows, "blowup", split),
            "ret_after_median_diff": med_diff_ci(rows, "ret_after", split)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = []
    for path in sorted(glob.glob(os.path.join(a.snapshots, "*.json"))):
        ts = os.path.basename(path)[:14]
        freeze = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        freeze_ms = int(freeze.timestamp() * 1000)
        with open(path, encoding="utf-8") as f:
            cohort = pick(json.load(f)["leaderboardRows"])
        for m in cohort:
            p = os.path.join(a.cache, m["address"] + ".json")
            if not os.path.exists(p):
                continue
            pf = fetch_portfolio(a.cache, m["address"])
            before = truncate(pf, freeze_ms)
            if len(before["allTime"]["accountValueHistory"]) < 2:
                continue
            tb = score(weekly_returns(before)[0])["t"]
            after_rets = weekly_returns(pf, since=freeze_ms)[0]
            ta = score(after_rets)["t"]
            if tb is None or ta is None:
                continue
            ret_after, dd_after = summed_path([r for r, _ in after_rets])
            rows.append({"snapshot": freeze.strftime("%Y-%m-%d"), "address": m["address"], "board": m["board"],
                         "t_before": tb, "t_after": ta, "ret_after": round(ret_after, 4),
                         "dd_after": round(dd_after, 4), "blowup": dd_after >= 0.35, **gates(before, freeze_ms)})

    ed = lambda r: r["t_before"] >= 2
    g1 = [r for r in rows if r["g1"]]
    g2 = [r for r in rows if r["g2"]]
    prim = compare(g1, ed, "inside G1: t_before >= 2 vs < 2")
    d, ci = prim["t_after_median_diff"]
    small = prim["yes"]["n"] < 20 or prim["no"]["n"] < 20
    if small:
        verdict = "not enough data"
    elif d is not None and d <= 0:
        verdict = "adds nothing"
    elif ci and ci[0] > 0:
        verdict = "adds to the gate"
    else:
        verdict = "inconclusive"
    out = {
        "prereg": "docs/data/hl/gates/PREREG.md",
        "scored_wallet_snapshots": len(rows), "wallets": len({r["address"] for r in rows}),
        "primary": prim, "verdict": verdict,
        "secondary": {
            "inside_G2": compare(g2, ed, "inside G2: t_before >= 2 vs < 2"),
            "G1_itself": compare(rows, lambda r: r["g1"], "G1 pass vs fail"),
            "G2_itself": compare(rows, lambda r: r["g2"], "G2 pass vs fail"),
            "G1_pass_clearing_bar200": sum(r["t_before"] >= BAR200 for r in g1),
            "G2_pass_clearing_bar200": sum(r["t_before"] >= BAR200 for r in g2),
            "G1_pass": len(g1), "G2_pass": len(g2),
        },
        "rows": rows,
    }
    s = json.dumps(out, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
