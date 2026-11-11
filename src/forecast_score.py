"""Score calls written down before the outcome: is this person's judgment better than a reference?

A trading record mixes two things: whether the calls were right, and what was done with
them (size, timing, exits). P&L needs years to separate skill from luck. A probability
written before the outcome can be scored as soon as the outcome is known, with a proper
scoring rule (one that rewards reporting what you actually believe), so judgment can be
tested on far fewer events than P&L can.

Input: one row per call, with `p` (probability the event happens, written beforehand) and
`outcome` (1 or 0). Optional `ref`: a reference probability for the same event at the same
time (a market price, a consensus); without it the reference is a coin flip, 0.5, which is
a low bar and is labelled as such. Optional `pnl`: what the trade on that call made, so
judgment and trading are scored side by side rather than mixed.

Skill is the mean over calls of (Brier of reference - Brier of the call). Its t uses the
per-call differences, so it asks the same question as the wallet check ("could this be
luck?") with the same bars: 2 for one record, the best-of-N bar when the record is the
best of N tried (several categories, several people, several prompts).

Standard library only.
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional

_N = statistics.NormalDist()
ALPHA = 1 - _N.cdf(2)
EPS = 1e-6


def bar(n: int = 1) -> float:
    """Same bar as hl_wallet.bar: 2 for one record, Bonferroni for the best of n."""
    return _N.inv_cdf(1 - ALPHA / max(n, 1))


def _clip(p: float) -> float:
    return min(max(p, EPS), 1 - EPS)


def parse(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        p = float(r["p"])
        if p > 1:  # written as a percentage
            p /= 100
        o = int(float(r["outcome"]))
        if not 0 <= p <= 1 or o not in (0, 1):
            raise ValueError("p must be in [0, 1] (or 0-100) and outcome 0 or 1: %r" % (r,))
        ref = r.get("ref")
        ref = None if ref in (None, "") else float(ref) / (100 if float(ref) > 1 else 1)
        pnl = r.get("pnl")
        pnl = None if pnl in (None, "") else float(pnl)
        out.append({"p": p, "o": o, "ref": ref, "pnl": pnl})
    return out


def calibration(calls: List[Dict[str, Any]], bins: int = 10) -> Dict[str, Any]:
    """Murphy's decomposition: Brier = reliability - resolution + uncertainty.

    reliability: how far stated probabilities sit from how often things happened at that
    probability (0 is perfect). resolution: how much the calls separate events that
    happen from those that do not. Per-bin table included for a calibration plot.
    """
    n = len(calls)
    base = sum(c["o"] for c in calls) / n
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for c in calls:
        groups.setdefault(min(int(c["p"] * bins), bins - 1), []).append(c)
    rel = res = 0.0
    table = []
    for k in sorted(groups):
        g = groups[k]
        pk = statistics.fmean(c["p"] for c in g)
        ok = statistics.fmean(c["o"] for c in g)
        rel += len(g) * (pk - ok) ** 2
        res += len(g) * (ok - base) ** 2
        table.append({"bin": "%.1f-%.1f" % (k / bins, (k + 1) / bins), "n": len(g),
                      "said": round(pk, 3), "happened": round(ok, 3)})
    return {"reliability": round(rel / n, 5), "resolution": round(res / n, 5),
            "uncertainty": round(base * (1 - base), 5), "base_rate": round(base, 4), "table": table}


def _t(xs: List[float]) -> Optional[Dict[str, float]]:
    if len(xs) < 2:
        return None
    m = statistics.fmean(xs)
    sd = statistics.stdev(xs)
    if sd == 0:
        return None
    return {"mean": m, "sd": sd, "t": m / (sd / math.sqrt(len(xs)))}


def score(calls: List[Dict[str, Any]], picked_from: int = 1) -> Dict[str, Any]:
    n = len(calls)
    if n == 0:
        raise ValueError("no calls")
    brier = statistics.fmean((c["p"] - c["o"]) ** 2 for c in calls)
    logs = statistics.fmean(-math.log(_clip(c["p"]) if c["o"] else 1 - _clip(c["p"])) for c in calls)
    has_ref = all(c["ref"] is not None for c in calls)
    ref_name = "given reference" if has_ref else "coin flip (0.5), a low bar"
    d = [((c["ref"] if has_ref else 0.5) - c["o"]) ** 2 - (c["p"] - c["o"]) ** 2 for c in calls]
    sk = _t(d)
    b = bar(picked_from)
    out: Dict[str, Any] = {"calls": n, "brier": round(brier, 5), "log_score": round(logs, 5),
                           "reference": ref_name, "calibration": calibration(calls), "bar": round(b, 2)}
    if sk is None:
        out["skill"] = None
        out["verdict"] = "too_few" if n < 2 else "no_spread"
        return out
    t = sk["t"]
    out["skill"] = {"brier_gain_per_call": round(sk["mean"], 5), "t": round(t, 3),
                    # calls needed for this gain to reach the bar, if it is real and stays this size
                    "calls_needed": (math.ceil((b * sk["sd"] / sk["mean"]) ** 2) if sk["mean"] > 0 else None)}
    out["verdict"] = ("clears" if t >= b else "worse_than_reference" if t <= -2 else "could_be_luck")
    pnl = [c["pnl"] for c in calls if c["pnl"] is not None]
    if len(pnl) >= 2:
        pt = _t(pnl)
        out["trading"] = {"calls_with_pnl": len(pnl), "t": (round(pt["t"], 3) if pt else None),
                          "note": "scored apart from judgment: good calls traded badly, or the reverse, show up here"}
    return out


def main(argv: Optional[List[str]] = None) -> None:
    import argparse
    import json
    ap = argparse.ArgumentParser(prog="python -m forecast_score",
                                 description="Score probabilities written before the outcome (CSV columns p, outcome, optional ref, pnl).")
    ap.add_argument("csv")
    ap.add_argument("--picked-from", type=int, default=1,
                    help="this record is the best of N tried (categories, people, prompts)")
    a = ap.parse_args(argv)
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        calls = parse(csv.DictReader(f))
    json.dump(score(calls, a.picked_from), sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
