"""Fetch Olas prediction-agent bets with their market resolutions (see docs/data/olas/PREDICT_AGENTS_PREREG.md).

Writes JSON lines, one file per venue and entity, to OUT_DIR, and resumes from the last id
already written (a half-written last line is dropped). Each bet carries its market's
resolution as of the moment its page was fetched. Omen is a graph-node subgraph, Polymarket
an SQD squid; both are paged by id. Standard library only.

    python tools/olas_fetch.py OUT_DIR [omen|poly|all]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

URL = {
    "omen": "https://api.subgraph.autonolas.tech/api/proxy/predict-omen",
    "poly": "https://subgraph.autonolas.tech/squid/predict-polymarket/graphql",
}
PAGE = {"omen": 1000, "poly": 500}
FIELDS = {
    ("omen", "agents"): ("traderAgents", "id serviceId firstParticipation totalBets"),
    ("omen", "bets"): ("bets", "id bettor { id } fixedProductMarketMaker { id currentAnswer currentAnswerTimestamp } "
                               "outcomeIndex amount feeAmount outcomeTokenAmount impliedProbability timestamp"),
    ("poly", "agents"): ("traderAgents", "id serviceId firstParticipation totalBets"),
    ("poly", "bets"): ("bets", "id bettor { id } question { id isNegRisk resolution { winningIndex payouts blockTimestamp } } "
                               "outcomeIndex amount shares isBuy impliedProbability blockTimestamp"),
}


def post(url: str, query: str, tries: int = 12) -> dict:
    body = json.dumps({"query": query}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, body, {"content-type": "application/json",
                                                     "user-agent": "evidence-deflator-research"})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            if d.get("errors"):
                raise RuntimeError(d["errors"])
            return d["data"]
        except Exception as e:  # network or server error: back off and retry
            wait = min(60, 2 ** i)
            print("retry %d after %ss: %s" % (i + 1, wait, str(e)[:200]), file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError("gave up on %s" % url)


def resume(path: str):
    """Last complete id and line count; truncates a half-written last line."""
    if not os.path.exists(path):
        return None, 0
    with open(path, "rb") as f:
        data = f.read()
    keep = data[: data.rfind(b"\n") + 1]
    if len(keep) != len(data):
        with open(path, "wb") as f:
            f.write(keep)
    lines = keep.splitlines()
    return (json.loads(lines[-1])["id"] if lines else None), len(lines)


def fetch(venue: str, kind: str, out_dir: str) -> int:
    path = os.path.join(out_dir, "%s_%s.jsonl" % (venue, kind))
    last, n = resume(path)
    entity, fields = FIELDS[(venue, kind)]
    with open(path, "a", encoding="utf-8") as f:
        while True:
            where = ', where: {id_gt: "%s"}' % last if last else ""
            if venue == "omen":
                q = "{ %s(first: %d, orderBy: id, orderDirection: asc%s) { %s } }" % (entity, PAGE[venue], where, fields)
            else:
                q = "{ %s(limit: %d, orderBy: id_ASC%s) { %s } }" % (entity, PAGE[venue], where, fields)
            rows = post(URL[venue], q)[entity]
            f.write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
            f.flush()
            n += len(rows)
            if rows:
                last = rows[-1]["id"]
            print("%s %s %d %s" % (venue, kind, n, time.strftime("%H:%M:%S")), flush=True)
            if len(rows) < PAGE[venue]:
                return n
            time.sleep(0.2)


def main(argv):
    out_dir = argv[1]
    which = argv[2] if len(argv) > 2 else "all"
    os.makedirs(out_dir, exist_ok=True)
    meta = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for v in (["poly", "omen"] if which == "all" else [which]):
        for kind in ("agents", "bets"):
            meta["%s_%s" % (v, kind)] = fetch(v, kind, out_dir)
    meta["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out_dir, "fetch_meta_%s.json" % which), "w") as f:
        json.dump(meta, f, indent=1)
    print(meta, flush=True)


if __name__ == "__main__":
    main(sys.argv)
