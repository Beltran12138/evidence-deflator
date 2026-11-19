"""Robustness check: score Hyperliquid board wallets as entities (master + sub-accounts).

Usage:
    python tools/hl_entity_merge.py BOARD_JSON CACHE_DIR OUT_JSON

For every board wallet that has sub-accounts, fetch the master's and each
sub-account's portfolio, merge them, and score the merged record with the
wallet check's own estimator. Merging: on the union of all sample times, each
account's account value and cumulative PnL are carried forward from its last
sample (0 before its first); the entity's value and PnL are the sums. Weekly
returns are then change in summed PnL over summed value at the start, exactly
as for one wallet. Transfers between master and sub move value, not PnL, so
they do not count as returns.

This is a robustness check on the published board, not a pre-registered test.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from hl_wallet import INFO_URL, bar, score, weekly_returns  # noqa: E402

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def info(body, cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(INFO_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "evidence-deflator"})
    err = None
    for i in range(4):
        try:
            with OPENER.open(req, timeout=60) as r:
                data = json.loads(r.read())
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            time.sleep(0.3)
            return data
        except Exception as e:
            err = e
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"{body['type']} failed: {err}")


def merge(pfs):
    """Sum account value and cumulative PnL across accounts on the union of sample times."""
    series = []
    for pf in pfs:
        at = pf.get("allTime") or {}
        av = sorted((t, float(v)) for t, v in at.get("accountValueHistory", []))
        pn = dict((t, float(v)) for t, v in at.get("pnlHistory", []))
        if av:
            series.append((av, pn))
    times = sorted({t for av, _ in series for t, _ in av})
    out_av, out_pnl = [], []
    idx = [0] * len(series)
    last = [(0.0, 0.0)] * len(series)
    for t in times:
        tv = tp = 0.0
        for k, (av, pn) in enumerate(series):
            while idx[k] < len(av) and av[idx[k]][0] <= t:
                ts, v = av[idx[k]]
                last[k] = (v, pn.get(ts, last[k][1]))
                idx[k] += 1
            tv += last[k][0]
            tp += last[k][1]
        out_av.append([t, str(tv)])
        out_pnl.append([t, str(tp)])
    return {"allTime": {"accountValueHistory": out_av, "pnlHistory": out_pnl}}


def main():
    board_path, cache, out = sys.argv[1:4]
    with open(board_path, encoding="utf-8") as f:
        d = json.load(f)
    res = {"source": board_path, "fetched_utc": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "boards": {}}
    for name in ("pnl", "roi30"):
        b = d["boards"][name]
        n = b["ranked_from"]
        bb = bar(n)
        rows = []
        for r in b["rows"]:
            a = r["address"].lower()
            subs = info({"type": "subAccounts", "user": a}, os.path.join(cache, "subs", a + ".json"))
            if not isinstance(subs, list) or not subs:
                continue
            master = info({"type": "portfolio", "user": a}, os.path.join(cache, "portfolio", a + ".json"))
            sub_pfs = []
            for s in subs:
                sa = s["subAccountUser"].lower()
                p = info({"type": "portfolio", "user": sa}, os.path.join(cache, "portfolio", sa + ".json"))
                if isinstance(p, list) and p:
                    sub_pfs.append(dict(p))
            m_only = score(weekly_returns(dict(master))[0]) if isinstance(master, list) and master else {"t": None}
            ent = score(weekly_returns(merge([dict(master)] + sub_pfs))[0]) if isinstance(master, list) and master else {"t": None}
            rows.append({"rank": r["rank"], "address": a, "n_subaccounts": len(subs), "n_sub_with_history": len(sub_pfs),
                         "t_published": r.get("t"), "t_master_today": m_only.get("t"), "weeks_master": m_only.get("weeks"),
                         "t_entity": ent.get("t"), "weeks_entity": ent.get("weeks"),
                         "clears_master": m_only.get("t") is not None and m_only["t"] >= bb,
                         "clears_entity": ent.get("t") is not None and ent["t"] >= bb})
        res["boards"][name] = {"ranked_from": n, "bar": round(bb, 2), "n_with_subaccounts": len(rows),
                               "n_clear_master": sum(x["clears_master"] for x in rows),
                               "n_clear_entity": sum(x["clears_entity"] for x in rows), "rows": rows}
        print(name, {k: v for k, v in res["boards"][name].items() if k != "rows"})
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
