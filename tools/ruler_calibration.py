"""Run the ruler calibration pre-registered in docs/data/hl/RULER_CALIBRATION_PREREG.md.

    python tools/ruler_calibration.py            # fetch the 200 cohort portfolios, then score
    python tools/ruler_calibration.py --cached   # re-score from the saved weekly returns

Saves the weekly returns it scored to docs/data/hl/calibration/returns-<date>.json (public data,
so the run can be repeated without the network) and the result to results-<date>.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet  # noqa: E402

COHORT = os.path.join(ROOT, "docs", "data", "hl", "cohort-2026-10-14.json")
OUT = os.path.join(ROOT, "docs", "data", "hl", "calibration")
N = statistics.NormalDist()
SEED, DRAWS = 20261021, 200


def fetch_all():
    members = json.load(open(COHORT, encoding="utf-8"))["members"]
    rows = []
    for k, m in enumerate(members):
        for attempt in range(4):
            try:
                pf = hl_wallet.fetch_portfolio(m["address"])
                rets, _, _, _ = hl_wallet.weekly_returns(pf)
                rows.append({"address": m["address"], "returns": rets})
                break
            except Exception as e:  # recorded as missing, not retried forever
                if attempt == 3:
                    rows.append({"address": m["address"], "returns": None, "error": str(e)[:200]})
                time.sleep(2 + 2 * attempt)
        time.sleep(0.3)
        if k % 25 == 24:
            print(f"fetched {k + 1}/{len(members)}", flush=True)
    return rows


def run(rows):
    usable = [r for r in rows if r["returns"] and len(r["returns"]) >= hl_wallet.MIN_WEEKS]
    rng = random.Random(SEED)
    cells = {"all": [0, 0], "8-25": [0, 0], "26-51": [0, 0], "52+": [0, 0]}
    hi = [0, 0]
    det, pred = [], []
    for r in usable:
        rets = r["returns"]
        n = len(rets)
        band = "8-25" if n < 26 else ("26-51" if n < 52 else "52+")
        weeks = sum(w for _, w in rets)
        sd = statistics.pstdev([x / math.sqrt(w) for x, w in rets]) or 0.0  # per sqrt(week)
        drift = 2 / math.sqrt(52) * sd                                     # annual Sharpe 2
        hits = 0
        for _ in range(DRAWS):
            flipped = [(x * (1 if rng.random() < 0.5 else -1), w) for x, w in rets]
            t = hl_wallet.score(flipped)["t"]
            if t is None:
                continue
            for c in ("all", band):
                cells[c][1] += 1
                cells[c][0] += t >= 2
            hi[1] += 1
            hi[0] += t >= 3.5
            t2 = hl_wallet.score([(x + drift * w, w) for x, w in flipped])["t"]
            hits += (t2 or -9) >= 2
        det.append(hits / DRAWS)
        pred.append(N.cdf(2 * math.sqrt(weeks / 52) - 2))
    rate = {k: (v[0] / v[1] if v[1] else None) for k, v in cells.items()}
    p = rate["all"]
    verdict = "anti-conservative" if p > 0.0455 else ("conservative" if p < 0.01138 else "calibrated")
    ratio = (sum(det) / len(det)) / (sum(pred) / len(pred)) if det else None
    return {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "seed": SEED, "draws": DRAWS,
        "wallets": len(rows), "usable": len(usable), "left_out": len(rows) - len(usable),
        "test1_sign_flip": {"pass_rate_t_ge_2": p, "nominal": 0.02275, "verdict": verdict,
                            "by_length": {k: rate[k] for k in ("8-25", "26-51", "52+")},
                            "n_by_length": {k: cells[k][1] for k in ("8-25", "26-51", "52+")},
                            "pass_rate_t_ge_3_5": hi[0] / hi[1] if hi[1] else None, "nominal_3_5": 1 - N.cdf(3.5)},
        "test2_power_sharpe_2": {"detected": sum(det) / len(det), "predicted": sum(pred) / len(pred),
                                 "ratio": ratio, "flag": (ratio is not None and ratio < 0.7)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if a.cached:
        rows = json.load(open(a.cached, encoding="utf-8"))["rows"]
    else:
        rows = fetch_all()
        with open(os.path.join(OUT, f"returns-{day}.json"), "w", encoding="utf-8") as f:
            json.dump({"fetched": day, "source": "Hyperliquid info API portfolio allTime, hl_wallet.weekly_returns",
                       "rows": rows}, f, separators=(",", ":"))
    res = run(rows)
    with open(os.path.join(OUT, f"results-{day}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
