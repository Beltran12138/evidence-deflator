"""Run the shrinkage test pre-registered in docs/data/hl/SHRINK_PREREG.md.

    python tools/shrink_test.py freeze   # now: fit the spread of skill from a random sample of
                                         # leaderboard wallets and fix every cohort wallet's
                                         # shrunk estimate, using only records up to the freeze
    python tools/shrink_test.py read     # 2026-12-09: score the cohort after the freeze and
                                         # compare shrunk with raw, as pre-registered

`freeze` writes docs/data/hl/shrink/prior.json and estimates.json. Those two files are the
pre-registered predictions: they are committed before the reading and not rewritten.
`read` writes docs/data/hl/shrink/reading-<date>.json. Portfolios are cached in .hlcache-shrink/.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import hl_wallet  # noqa: E402
import shrink  # noqa: E402
from build_hl_board import fetch_leaderboard, fetch_portfolio  # noqa: E402

COHORT = os.path.join(ROOT, "docs", "data", "hl", "cohort-2026-10-14.json")
OUT = os.path.join(ROOT, "docs", "data", "hl", "shrink")
CACHE = os.path.join(ROOT, ".hlcache-shrink")
SAMPLE_SEED, SAMPLE_N = 20261110, 1500
BOOT_SEED, BOOT_N = 20261209, 10000


def until(pf, cut_ms):
    """The portfolio as it would have looked at cut_ms: drop every later sample."""
    a = pf["allTime"]
    return {"allTime": {"accountValueHistory": [p for p in a["accountValueHistory"] if p[0] <= cut_ms],
                        "pnlHistory": [p for p in a["pnlHistory"] if p[0] <= cut_ms]}}


def score_before(pf, cut_ms):
    rets, _, _, _ = hl_wallet.weekly_returns(until(pf, cut_ms))
    sc = hl_wallet.score(rets)
    return (sc["t"], sc["weeks"] / 52) if sc.get("t") is not None else (None, None)


def score_after(pf, cut_ms):
    rets, _, _, _ = hl_wallet.weekly_returns(pf, since=cut_ms)
    sc = hl_wallet.score(rets)
    return (sc["t"], sc["weeks"] / 52) if sc.get("t") is not None else (None, None)


def get(addr, refresh):
    for attempt in range(4):
        try:
            return fetch_portfolio(CACHE, addr, refresh and attempt == 0)
        except Exception:  # network hiccup: retry, then give up on this wallet
            if attempt == 3:
                return None
    return None


def sample_addresses(refresh):
    rows = fetch_leaderboard(CACHE, refresh)
    addrs = sorted({r["ethAddress"].lower() for r in rows})
    rnd = random.Random(SAMPLE_SEED)
    return len(addrs), rnd.sample(addrs, min(SAMPLE_N, len(addrs)))


def freeze(args):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    co = json.load(open(COHORT, encoding="utf-8"))
    cut = co["frozen_at_ms"]
    members = co["members"]
    board_n, sample = sample_addresses(args.refresh)

    obs, kept, failed = [], [], 0
    for k, a in enumerate(sample):
        pf = get(a, args.refresh)
        if pf is None:
            failed += 1
            continue
        z, y = score_before(pf, cut)
        if z is not None:
            obs.append((z, y))
            kept.append({"address": a, "z": z, "years": round(y, 4)})
        if k % 100 == 99:
            print(f"sample {k + 1}/{len(sample)} usable {len(obs)} failed {failed}", flush=True)
    prior = shrink.fit_prior(obs)
    summ = shrink.prior_summary(prior)
    json.dump({"frozen_at": co["frozen_at"], "made": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
               "board_accounts": board_n, "sample_seed": SAMPLE_SEED, "sampled": len(sample),
               "fetch_failed": failed, "usable": len(obs), "summary": summ,
               "grid": prior["grid"], "weights": [round(x, 10) for x in prior["weights"]],
               "sample": kept}, open(os.path.join(OUT, "prior.json"), "w", encoding="utf-8"), indent=0)

    est, missing = [], 0
    for m in members:
        pf = get(m["address"], args.refresh)
        z, y = score_before(pf, cut) if pf is not None else (None, None)
        if z is None:
            missing += 1
            est.append({"address": m["address"], "board": m["board"], "t_before_stored": m["t_before"], "z": None})
            continue
        p = shrink.posterior(z, y, prior)
        est.append({"address": m["address"], "board": m["board"], "t_before_stored": m["t_before"],
                    "z": z, "years": round(y, 4), **{k: p[k] for k in ("raw", "mean", "lo", "hi", "p_positive", "shrunk")}})
    json.dump({"frozen_at": co["frozen_at"], "prior_file": "prior.json", "level": 0.9, "no_estimate": missing,
               "members": est}, open(os.path.join(OUT, "estimates.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({"board_accounts": board_n, "usable": len(obs), "failed": failed, "prior": summ,
                      "cohort_estimated": len(members) - missing}, indent=1))


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def boot(rows, stat):
    rnd = random.Random(BOOT_SEED)
    n = len(rows)
    vals = sorted(stat([rows[rnd.randrange(n)] for _ in range(n)]) for _ in range(BOOT_N))
    return [round(vals[int(0.025 * BOOT_N)], 4), round(vals[int(0.975 * BOOT_N) - 1], 4)]


def read(args):
    co = json.load(open(COHORT, encoding="utf-8"))
    cut = co["frozen_at_ms"]
    pr_file = json.load(open(os.path.join(OUT, "prior.json"), encoding="utf-8"))
    prior = {"grid": pr_file["grid"], "weights": pr_file["weights"]}
    est = json.load(open(os.path.join(OUT, "estimates.json"), encoding="utf-8"))["members"]

    rows, left_out = [], 0
    for e in est:
        if e.get("z") is None:
            left_out += 1
            continue
        pf = get(e["address"], True)
        za, ya = score_after(pf, cut) if pf is not None else (None, None)
        if za is None:
            left_out += 1
            continue
        pred = shrink.predictive(e["z"], e["years"], prior, ya)
        rows.append({"address": e["address"], "board": e["board"], "z_before": e["z"], "raw": e["raw"],
                     "mean": e["mean"], "z_after": za, "years_after": round(ya, 4),
                     "e_raw": za - e["raw"] * math.sqrt(ya), "e_shrunk": za - e["mean"] * math.sqrt(ya),
                     "in_interval": pred["lo"] <= za <= pred["hi"]})

    res = {"read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "n": len(rows), "left_out": left_out}
    if len(rows) < 30:
        res["verdict"] = "not enough data: reading moves to 2027-01-06 under the same rules"
    else:
        def d_mse(rs):
            return statistics.fmean(r["e_raw"] ** 2 for r in rs) - statistics.fmean(r["e_shrunk"] ** 2 for r in rs)

        def d_rho(rs):
            za = [r["z_after"] for r in rs]
            return spearman([r["mean"] for r in rs], za) - spearman([r["z_before"] for r in rs], za)

        p1, p1_ci = d_mse(rows), boot(rows, d_mse)
        p2, p2_ci = d_rho(rows), boot(rows, d_rho)
        if p1_ci[0] > 0 and p2_ci[1] >= 0:
            v = "ship: shrunk estimate predicts better and ranks no worse"
            if p2_ci[0] > 0:
                v += "; it also ranks better, so it may replace raw t for ranking"
        elif p1_ci[1] < 0:
            v = "shrinkage predicts worse: do not ship, say so on the record page"
        elif p1_ci[0] > 0:
            v = "shrinkage predicts better but ranks worse: do not ship"
        else:
            v = "inconclusive: do not ship; read once more on 2027-02-03 with the same frozen estimates"
        za = [r["z_after"] for r in rows]
        res.update({
            "P1_mse_raw_minus_shrunk": round(p1, 4), "P1_ci95": p1_ci,
            "mse_raw": round(statistics.fmean(r["e_raw"] ** 2 for r in rows), 4),
            "mse_shrunk": round(statistics.fmean(r["e_shrunk"] ** 2 for r in rows), 4),
            "P2_rho_shrunk_minus_rho_t": round(p2, 4), "P2_ci95": p2_ci,
            "rho_shrunk": round(spearman([r["mean"] for r in rows], za), 4),
            "rho_t_before": round(spearman([r["z_before"] for r in rows], za), 4),
            "rho_raw_sharpe": round(spearman([r["raw"] for r in rows], za), 4),
            "mean_error_raw": round(statistics.fmean(r["e_raw"] for r in rows), 4),
            "mean_error_shrunk": round(statistics.fmean(r["e_shrunk"] for r in rows), 4),
            "interval90_coverage": round(statistics.fmean(1.0 if r["in_interval"] else 0.0 for r in rows), 4),
            "verdict": v})
    res["rows"] = rows
    path = os.path.join(OUT, "reading-%s.json" % datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    json.dump(res, open(path, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["freeze", "read"])
    ap.add_argument("--refresh", action="store_true", help="refetch instead of using .hlcache-shrink")
    a = ap.parse_args()
    (freeze if a.mode == "freeze" else read)(a)


if __name__ == "__main__":
    main()
