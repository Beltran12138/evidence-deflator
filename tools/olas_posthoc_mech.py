"""Post-hoc (NOT pre-registered): the Olas test again, with each Omen agent's mech (tool) cost.

Written after the pre-registered run showed hundreds of Omen agents beating their prices
before tool costs. Olas's own ROI charges 0.01 xDAI per mech request and counts requests as
`Sender.totalLegacyRequests` (olas-website common-util/api/predict/roi-math.ts,
DEFAULT_MECH_FEE in common-util/constants.ts). Here an agent's lifetime mech cost is shared
over its resolved markets in proportion to its bets in them (bets in resolved markets / all
its bets), spread evenly across those markets, and subtracted from each market's profit.
Same N, bar and minimum markets as the pre-registered test. Standard library.

    python tools/olas_posthoc_mech.py DATA_DIR OUT_JSON
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import olas_predict_test as t  # noqa: E402

MECH_FEE = 0.01  # xDAI per request, as Olas books it


def main(argv):
    d, out_path = argv[1], argv[2]
    bets = list(t.load(os.path.join(d, "omen_bets.jsonl")))
    pos = t.positions(bets, "omen")
    rows = t.returns(pos, "omen")
    resolved = {(r["agent"], r["market"]) for r in rows}
    bets_all, bets_res = Counter(), Counter()
    for b in bets:
        a = b["bettor"]["id"]
        m = (b.get("fixedProductMarketMaker") or {}).get("id")
        bets_all[a] += 1
        if (a, m) in resolved:
            bets_res[a] += 1
    del bets
    mech = {}
    for line in open(os.path.join(d, "omen_mech.jsonl"), encoding="utf-8"):
        s = json.loads(line)
        mech[s["id"]] = int(s["totalLegacyRequests"]) * MECH_FEE
    n_bar_rows = rows + [r for r in t.returns(t.positions(t.load(os.path.join(d, "poly_bets.jsonl")), "poly"), "poly")]
    n_bar = len({(r["venue"], r["agent"]) for r in n_bar_rows})
    bar = t.bar(n_bar)

    by = defaultdict(list)
    for r in rows:
        by[r["agent"]].append(r)
    table = []
    tot = {"paid": 0.0, "profit": 0.0, "mech": 0.0}
    for a, rs in by.items():
        M = len(rs)
        share = bets_res[a] / bets_all[a] if bets_all[a] else 0.0
        alloc = mech.get(a, 0.0) * share
        per_market = alloc / M
        paid_m = [pos[(a, r["market"])]["paid"] for r in rs]
        R_net = [r["R"] - per_market / pm for r, pm in zip(rs, paid_m)]
        profit = sum(r["R"] * pm for r, pm in zip(rs, paid_m))
        tot["paid"] += sum(paid_m)
        tot["profit"] += profit
        tot["mech"] += alloc
        if M < t.MIN_MARKETS:
            continue
        table.append({"agent": a, "M": M, "paid": sum(paid_m), "profit_before_mech": profit,
                      "mech_alloc": alloc, "has_mech_record": a in mech,
                      "roi_before": profit / sum(paid_m), "roi_after": (profit - alloc) / sum(paid_m),
                      "t_before": t.t_stat([r["R"] for r in rs]), "t_after": t.t_stat(R_net)})
    with_t = [x for x in table if x["t_after"] is not None]
    res = {"N_bar": n_bar, "bar": bar, "eligible": len(table),
           "pass_before": sum((x["t_before"] or 0) >= bar for x in table),
           "pass_after": sum(x["t_after"] >= bar for x in with_t),
           "pass_2_after": sum(x["t_after"] >= 2 for x in with_t),
           "eligible_without_mech_record": sum(not x["has_mech_record"] for x in table),
           "fleet_resolved": {"paid": tot["paid"], "profit_before_mech": tot["profit"], "mech_alloc": tot["mech"],
                              "roi_before": tot["profit"] / tot["paid"],
                              "roi_after": (tot["profit"] - tot["mech"]) / tot["paid"]},
           "median_roi_before": statistics.median(x["roi_before"] for x in table),
           "median_roi_after": statistics.median(x["roi_after"] for x in table),
           "top5_after": sorted(with_t, key=lambda x: -x["t_after"])[:5],
           "table": sorted(table, key=lambda x: -(x["t_after"] or -1e9))}
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "table"}, indent=1))


if __name__ == "__main__":
    main(sys.argv)
