"""Post-hoc (not pre-registered): fetch each Olas trader agent's lifetime mech (tool) costs.

Agents pay a "mech" for a prediction before most bets. The pre-registered test left this cost
out (docs/data/olas/PREDICT_AGENTS_PREREG.md, "What this does not test"); Olas's own ROI
includes it. Source: Olas marketplace subgraph on Gnosis, entity Sender (keyed by the agent's
Safe), fields totalFeesPaidUSD and request counts. Writes JSON lines to OUT. Standard library.

    python tools/olas_mech_costs.py AGENTS_JSONL OUT_JSONL
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

URL = "https://api.subgraph.autonolas.tech/api/proxy/marketplace-gnosis"
FIELDS = "id totalFeesPaidUSD totalMarketplaceRequests totalLegacyRequests totalOffChainRequests totalPredictRequests"


def post(q: str) -> dict:
    for i in range(10):
        try:
            req = urllib.request.Request(URL, json.dumps({"query": q}).encode(),
                                         {"content-type": "application/json", "user-agent": "evidence-deflator-research"})
            d = json.loads(urllib.request.urlopen(req, timeout=120).read())
            if d.get("errors"):
                raise RuntimeError(d["errors"])
            return d["data"]
        except Exception as e:
            print("retry", i, str(e)[:150], file=sys.stderr, flush=True)
            time.sleep(min(60, 2 ** i))
    raise RuntimeError("gave up")


def main(argv):
    ids = [json.loads(l)["id"] for l in open(argv[1], encoding="utf-8") if l.strip()]
    with open(argv[2], "w", encoding="utf-8") as f:
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            q = "{ senders(first: 100, where: {id_in: %s}) { %s } }" % (json.dumps(batch), FIELDS)
            for r in post(q)["senders"]:
                f.write(json.dumps(r) + "\n")
            print(i + len(batch), flush=True)


if __name__ == "__main__":
    main(sys.argv)
