"""The pre-registered flow test: do vault deposits follow record strength beyond last month's return?

    python tools/vault_flow_test.py HISTORIES_JSONL [--out RESULTS_JSON]

Implements docs/data/hl/VAULT_FLOW_PREREG.md as written on 2026-11-03, with Amendment 1 (same day,
before any outcome): the primary run has no rough-interval rule, and the original rule (share <= 0.10)
is a sensitivity run reported next to it. Nothing here may change a threshold. HISTORIES_JSONL comes from tools/fetch_vault_histories.py.

Month-end t is 00:00 UTC on the first day of the next month, for the months 2025-01 to 2026-09.
At each t, for each vault:
  AV(t), cumulative PnL(t)  linear interpolation between samples; after the last sample of a closed
                            vault, its last sample (the vault is gone, so are its deposits)
  eligible                  AV(t) >= 50,000 and at least 8 weekly returns up to t; in the sensitivity
                            run also a rough-interval share up to t of at most 0.10 (left-out counts
                            reported)
  F                         (dAV - dPnL) over (t, t + 30d] / AV(t), winsorised 1st/99th per month
  R                         curve return over the 30 days before t (vault_follower_gap.curve_return on
                            the samples up to t)
  S                         hl_wallet.score t-statistic of the weekly returns up to t
  L                         weeks of record up to t
Per month with >= 30 eligible vaults: Spearman rho(F, R) and partial Spearman rho(F, S | R) and
rho(F, L | R) (ranks residualised on rank R by least squares, then correlated). Means across months,
95% intervals from a bootstrap over months (2,000 draws, seed 20261103), and a within-month shuffle of
S (1,000 draws) as the negative control.
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import hl_wallet  # noqa: E402
import vault_follower_gap as vfg  # noqa: E402

DAY = 86400 * 1000
MIN_AV_T = 50_000.0
MIN_ROUGH = 0.10
MIN_MONTH_N = 30
THETA = 0.10
MIN_OBS = 300
SEED = 20261103


def month_ends(first=(2025, 1), last=(2026, 9)):
    y, m = first
    out = []
    while (y, m) <= last:
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append(int(dt.datetime(ny, nm, 1, tzinfo=dt.timezone.utc).timestamp() * 1000))
        y, m = ny, nm
    return out


def interp(series, t, closed):
    """Linear interpolation of a sorted [(ms, value)] series at t; None outside it, except after the last
    sample of a closed vault, where the last sample holds."""
    if not series or t < series[0][0]:
        return None
    if t >= series[-1][0]:
        return series[-1][1] if (closed or t == series[-1][0]) else None
    lo, hi = 0, len(series) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if series[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    (ta, va), (tb, vb) = series[lo], series[hi]
    return va + (vb - va) * (t - ta) / (tb - ta)


def observe(v, t, rough_max=None):
    """One vault at one month-end: dict of F, R, S, L, or a string saying why it is left out."""
    av = [(int(a), float(b)) for a, b in v["av"]]
    pnl_s = [(int(a), float(b)) for a, b in v["pnl"]]
    if len(av) < 2:
        return "no_history"
    a0, p0 = interp(av, t, v["closed"]), interp(pnl_s, t, v["closed"])
    if a0 is None or p0 is None:
        return "outside_history"
    if a0 < MIN_AV_T:
        return "below_50k"
    a1, p1 = interp(av, t + 30 * DAY, v["closed"]), interp(pnl_s, t + 30 * DAY, v["closed"])
    if a1 is None or p1 is None:
        return "outcome_outside_history"
    upto = [(a, b) for a, b in av if a <= t]
    pnl_upto = {a: b for a, b in pnl_s if a <= t}
    pf = {"allTime": {"accountValueHistory": [[a, b] for a, b in upto], "pnlHistory": [[a, b] for a, b in pnl_s if a <= t]}}
    rets, *_ = hl_wallet.weekly_returns(pf)
    sc = hl_wallet.score(rets)
    if sc.get("t") is None:
        return "under_8_weeks"
    if rough_max is not None:
        rough = vfg.rough_share(upto, pnl_upto, upto[0][0])
        if rough is None or rough > rough_max:
            return "rough"
    return {"F": ((a1 - a0) - (p1 - p0)) / a0, "R": vfg.curve_return(upto, pnl_upto, t - 30 * DAY),
            "S": sc["t"], "L": sc["weeks"]}


def ranks(x):
    """Average ranks (ties share the mean rank)."""
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[order] = np.arange(len(x), dtype=float)
    vals, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=r)
    return (sums / counts)[inv]


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def resid(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


def month_stats(F, R, S, L):
    rf, rr, rs, rl = ranks(F), ranks(R), ranks(S), ranks(L)
    ef = resid(rf, rr)
    return {"rho_FR": corr(rf, rr), "partial_FS_R": corr(ef, resid(rs, rr)), "partial_FL_R": corr(ef, resid(rl, rr))}


def winsor(x):
    lo, hi = np.percentile(x, [1, 99])
    return np.clip(x, lo, hi)


def bootstrap(values, rng, n=2000):
    v = np.asarray(values)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def run(vaults, rough_max=None, rng_seed=SEED):
    months, left_out, n_obs = [], {}, 0
    for t in month_ends():
        rows = []
        for v in vaults:
            o = observe(v, t, rough_max)
            if isinstance(o, str):
                left_out[o] = left_out.get(o, 0) + 1
            else:
                rows.append(o)
        label = dt.datetime.fromtimestamp((t - DAY) / 1000, dt.timezone.utc).strftime("%Y-%m")
        if len(rows) < MIN_MONTH_N:
            months.append({"month": label, "n": len(rows), "used": False})
            continue
        F = winsor(np.array([r["F"] for r in rows]))
        R, S, L = (np.array([r[k] for r in rows]) for k in "RSL")
        months.append({"month": label, "n": len(rows), "used": True, **month_stats(F, R, S, L), "_data": (F, R, S, L)})
        n_obs += len(rows)
    used = [m for m in months if m["used"]]
    rng = np.random.default_rng(rng_seed)
    out = {"months": [{k: v for k, v in m.items() if k != "_data"} for m in months], "left_out": left_out,
           "observations": n_obs, "months_used": len(used), "theta": THETA, "min_obs": MIN_OBS}
    if not used:
        out["decision"] = "underpowered"
        return out
    for key in ("rho_FR", "partial_FS_R", "partial_FL_R"):
        vals = [m[key] for m in used]
        out[key] = {"mean": float(np.mean(vals)), "ci95": bootstrap(vals, rng)}
    shuf = []
    for _ in range(1000):
        per = []
        for m in used:
            F, R, S, L = m["_data"]
            per.append(month_stats(F, R, rng.permutation(S), L)["partial_FS_R"])
        shuf.append(np.mean(per))
    real = out["partial_FS_R"]["mean"]
    out["shuffle_control"] = {"p2.5": float(np.percentile(shuf, 2.5)), "p50": float(np.percentile(shuf, 50)),
                              "p97.5": float(np.percentile(shuf, 97.5)),
                              "share_at_or_above_real": float(np.mean(np.array(shuf) >= real))}
    pos_ok = out["rho_FR"]["ci95"][0] > 0
    out["positive_control_passed"] = pos_ok
    if n_obs < MIN_OBS:
        out["decision"] = "underpowered"
    elif not pos_ok:
        out["decision"] = "no_conclusion_positive_control_failed"
    elif real >= THETA and out["partial_FS_R"]["ci95"][0] > 0:
        out["decision"] = "credibility_rewarded"
    else:
        out["decision"] = "not_rewarded"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("histories")
    ap.add_argument("--out")
    a = ap.parse_args()
    with open(a.histories, encoding="utf-8") as f:
        vaults = [json.loads(line) for line in f if line.strip()]
    out = {"vaults_loaded": len(vaults), "primary": run(vaults), "sensitivity_rough_0.10": run(vaults, rough_max=MIN_ROUGH),
           "decision": None}
    out["decision"] = out["primary"]["decision"]  # Amendment 1: decided on the primary run only
    s = json.dumps(out, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(s)


if __name__ == "__main__":
    main()
