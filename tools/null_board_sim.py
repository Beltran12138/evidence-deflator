"""What a Hyperliquid-sized board looks like when nobody has any skill.

    python tools/null_board_sim.py [--sims 200] [--seed 7] [--out docs/data/hl/null-sim.json]

Simulates N accounts (the board size in docs/data/hl/latest.json) with zero expected return, ranks
them the way Hyperliquid's leaderboard does (all-time PnL; 30-day ROI among accounts of $10k or more),
takes the top 100 of each, and scores each record with the wallet check's estimator (weekly returns,
Student-t put on the normal scale). The question it answers: on a board ranked by profit, how often
does luck alone produce "promising" (t >= 2) and "strong" (t >= bar) records, compared with what the
real board shows?

Each account: a record length drawn from the lengths observed on today's two top-100 boards (top
accounts are older than average, so this leans toward longer records, which only helps luck), an
account size from a log-normal (median $30k, wide), a weekly volatility from a log-normal (median 8%),
and weekly returns from a Student t with 3 degrees of freedom (fat tails), scaled to that volatility,
mean zero. PnL is return times size each week. These are assumptions, stated so they can be argued
with; the script prints how the result moves when they change (--fat, --vol, --size-sigma).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from scipy import stats

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402


def z_scores(r):
    """Rows of weekly returns (NaN = before the record starts) -> t on the normal scale, as score()."""
    n = np.sum(~np.isnan(r), axis=1)
    mu = np.nanmean(r, axis=1)
    sd = np.nanstd(r, axis=1, ddof=1)
    t = mu / sd * np.sqrt(n)
    dof = n - 1
    p = stats.t.sf(t, dof)
    z = -stats.norm.ppf(np.clip(p, 1e-300, 1))
    z[n < hw.MIN_WEEKS] = np.nan
    return z


def one_board(rng, N, lengths, fat, vol_med, size_sigma, W):
    L = rng.choice(lengths, size=N)
    size = np.exp(rng.normal(math.log(30_000), size_sigma, N))
    vol = np.exp(rng.normal(math.log(vol_med), 0.6, N))
    raw = rng.standard_t(fat, size=(N, W)) / math.sqrt(fat / (fat - 2))
    r = raw * vol[:, None]
    mask = np.arange(W)[None, :] < (W - L)[:, None]  # record starts W - L weeks before now
    r[mask] = np.nan
    pnl = np.nansum(r, axis=1) * size
    roi30 = np.nansum(r[:, -4:], axis=1)
    out = {}
    top_pnl = np.argsort(-pnl)[:100]
    elig = np.where(size >= 10_000)[0]
    top_roi = elig[np.argsort(-roi30[elig])[:100]]
    for key, idx in (("pnl", top_pnl), ("roi30", top_roi)):
        z = z_scores(r[idx])
        zs = z[~np.isnan(z)]
        out[key] = {"scored": int(zs.size), "t_ge_2": int(np.sum(zs >= 2)), "max_t": float(np.max(zs)) if zs.size else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fat", type=float, default=3.0)
    ap.add_argument("--vol", type=float, default=0.08)
    ap.add_argument("--size-sigma", type=float, default=1.8)
    ap.add_argument("--out")
    a = ap.parse_args()
    with open(os.path.join(ROOT, "docs", "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    N = hl["boards"]["pnl"]["ranked_from"]
    bar = hw.bar(N)
    lengths = np.array([int(round(r["weeks"])) for k in ("pnl", "roi30") for r in hl["boards"][k]["rows"] if r.get("weeks")])
    lengths = lengths[lengths >= 1]
    W = int(lengths.max())
    rng = np.random.default_rng(a.seed)
    res = {"pnl": [], "roi30": []}
    for i in range(a.sims):
        b = one_board(rng, N, lengths, a.fat, a.vol, a.size_sigma, W)
        for k in res:
            res[k].append(b[k])
    obs = {k: {"scored": hl["boards"][k]["scored"], "t_ge_2": hl["boards"][k]["n_t_ge_2"],
               "max_t": max(r["t"] for r in hl["boards"][k]["rows"] if r["t"] is not None)} for k in res}
    summary = {}
    for k, runs in res.items():
        share = np.array([x["t_ge_2"] / x["scored"] for x in runs if x["scored"]])
        mx = np.array([x["max_t"] for x in runs if x["max_t"] is not None])
        o_share = obs[k]["t_ge_2"] / obs[k]["scored"]
        summary[k] = {
            "null_share_t_ge_2": {"median": round(float(np.median(share)), 4), "p5": round(float(np.percentile(share, 5)), 4),
                                  "p95": round(float(np.percentile(share, 95)), 4)},
            "null_max_t": {"median": round(float(np.median(mx)), 2), "p95": round(float(np.percentile(mx, 95)), 2)},
            "null_share_of_boards_with_any_t_ge_bar": round(float(np.mean(mx >= bar)), 4),
            "observed": {"share_t_ge_2": round(o_share, 4), **obs[k]},
            "observed_share_percentile_under_null": round(float(np.mean(share < o_share)), 4),
        }
    out = {"board_size": N, "bar": round(bar, 2), "sims": a.sims, "seed": a.seed,
           "assumptions": {"t_dof": a.fat, "weekly_vol_median": a.vol, "size_log_sigma": a.size_sigma,
                           "record_lengths": "drawn from today's top-100 boards", "weeks_grid": W},
           "fetched_board": hl["fetched"], "summary": summary, "doc": __doc__.strip()}
    print(json.dumps({k: v for k, v in out.items() if k != "doc"}, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
