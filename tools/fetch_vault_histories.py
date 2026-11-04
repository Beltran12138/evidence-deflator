"""Fetch the all-time account value and PnL history of every Hyperliquid vault, for the flow test.

    python tools/fetch_vault_histories.py VAULTS_JSON OUT_JSONL

VAULTS_JSON is a saved copy of stats-data.hyperliquid.xyz/Mainnet/vaults. Each line of OUT_JSONL is one
vault: address, name, closed flag, creation time, leader commission and the `allTime` portfolio window
from `info vaultDetails` (the only part the test uses; follower lists are not kept). Resumable: vaults
already in OUT_JSONL are skipped. HLP and its child vaults are skipped, and so are vaults created after
2026-08-05, which cannot have 8 weeks of record by the last month-end of the test (2026-09-30).
Paced at about one request a second (the info endpoint's weight budget); proxies in the environment
are bypassed.
"""
import json
import os
import sys
import time
import urllib.request

API = "https://api.hyperliquid.xyz/info"
CREATED_BY = 1785888000000  # 2026-08-05 00:00 UTC
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(body, tries=12):
    for k in range(tries):
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with OPENER.open(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # 429 or a dropped connection: back off and retry
            wait = min(60, 5 * (k + 1))  # rides out a few minutes of a dropped line
            print(f"retry {k + 1} in {wait}s: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"gave up: {body}")


def main():
    src, out = sys.argv[1], sys.argv[2]
    vaults = json.load(open(src, encoding="utf-8"))
    todo = [v["summary"] for v in vaults
            if v["summary"]["relationship"]["type"] == "normal" and v["summary"]["createTimeMillis"] <= CREATED_BY]
    done = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            done = {json.loads(line)["vault"] for line in f if line.strip()}
    print(f"{len(todo)} vaults, {len(done)} already fetched", flush=True)
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        for i, s in enumerate(todo):
            a = s["vaultAddress"]
            if a in done:
                continue
            t0 = time.time()
            d = post({"type": "vaultDetails", "vaultAddress": a})
            pf = dict(d.get("portfolio") or []).get("allTime") or {}
            f.write(json.dumps({"vault": a, "name": s["name"], "closed": s["isClosed"], "created": s["createTimeMillis"],
                                "commission": d.get("leaderCommission"),
                                "av": pf.get("accountValueHistory", []), "pnl": pf.get("pnlHistory", [])},
                               ensure_ascii=False) + "\n")
            f.flush()
            if i % 200 == 0:
                print(f"{i}/{len(todo)}", flush=True)
            time.sleep(max(0.0, 1.05 - (time.time() - t0)))
    print("done", flush=True)


if __name__ == "__main__":
    main()
