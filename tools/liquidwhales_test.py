"""Audit 017: do LiquidWhales' published S/A wallets clear the luck bar?

Usage:
    python tools/liquidwhales_test.py SNAPSHOT_DIR CACHE_DIR OUT_JSON

SNAPSHOT_DIR holds stats.json and grades_min_A.json as frozen by
docs/data/liquidwhales/LIQUIDWHALES_GRADES_PREREG.md. CACHE_DIR keeps the raw
Hyperliquid responses (outside the repo). Scores use the wallet check's own
estimator (src/hl_wallet.py: weekly_returns + score) on full history.
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from hl_wallet import INFO_URL, MIN_WEEKS, bar, score, weekly_returns  # noqa: E402

N_GRADED = 28623   # stats.json "graded" (pre-registered N)
N_TRACKED = 611093  # stats.json "tracked" (reported, no pass mark)
FAIL_AT = 14        # >= this many clearing bar(N_GRADED) means our critique fails


# Direct, like tools/build_hl_board.py: the local proxy rate-limits bursts (429).
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
            return data
        except Exception as e:  # network: retry, then record the failure
            err = e
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"{body['type']} failed: {err}")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


def one(w, cache):
    a = w["address"].lower()
    pf = info({"type": "portfolio", "user": a}, os.path.join(cache, "portfolio", a + ".json"))
    vault = info({"type": "vaultDetails", "vaultAddress": a}, os.path.join(cache, "vault", a + ".json"))
    role = info({"type": "userRole", "user": a}, os.path.join(cache, "role", a + ".json"))
    subs = info({"type": "subAccounts", "user": a}, os.path.join(cache, "subs", a + ".json"))
    row = {"address": a, "grade": w["grade"], "grade_score": w["grade_score"], "site_pnl": w["pnl_usd"],
           "site_sharpe": w["sharpe"], "site_days": w["days_active"],
           "is_vault": vault is not None,
           "role": role.get("role") if isinstance(role, dict) else None,
           "master": (role.get("data") or {}).get("master") if isinstance(role, dict) else None,
           "n_subaccounts": len(subs) if isinstance(subs, list) else 0}
    if not isinstance(pf, list) or not pf:
        row.update({"weeks": 0, "t": None, "excluded": "no portfolio"})
        return row
    rets, start, end, _ = weekly_returns(dict(pf))
    sc = score(rets)
    row.update(sc)
    row["history_from_ms"] = start
    if row["is_vault"]:
        row["excluded"] = "vault"
    elif sc.get("t") is None:
        row["excluded"] = f"fewer than {MIN_WEEKS} weekly intervals"
    return row


def main():
    snap, cache, out = sys.argv[1:4]
    with open(os.path.join(snap, "grades_min_A.json"), encoding="utf-8") as f:
        wallets = json.load(f)["whales"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        rows = list(ex.map(lambda w: one(w, cache), wallets))

    scored = [r for r in rows if "excluded" not in r]
    b_main, b_tracked, b_list = bar(N_GRADED), bar(N_TRACKED), bar(len(wallets))
    n_clear = sum(r["t"] >= b_main for r in scored)
    verdict = ("critique fails" if n_clear >= FAIL_AT else
               "as expected" if n_clear <= 1 else "no general claim")
    rho = spearman([r["grade_score"] for r in scored], [r["t"] for r in scored]) if len(scored) > 2 else None
    masters = {}
    for r in rows:
        if r["role"] == "subAccount":
            masters[r["master"]] = masters.get(r["master"], 0) + 1
    res = {
        "prereg": "docs/data/liquidwhales/LIQUIDWHALES_GRADES_PREREG.md",
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()),
        "n_list": len(wallets), "n_scored": len(scored),
        "excluded": {k: sum(1 for r in rows if r.get("excluded") == k)
                     for k in sorted({r["excluded"] for r in rows if "excluded" in r})},
        "primary": {"N": N_GRADED, "bar": round(b_main, 2), "n_clear": n_clear,
                    "expectation": "at most 1", "critique_fails_at": FAIL_AT, "verdict": verdict},
        "reported": {
            "n_clear_bar_tracked": {"N": N_TRACKED, "bar": round(b_tracked, 2),
                                    "n": sum(r["t"] >= b_tracked for r in scored)},
            "n_clear_bar_list": {"N": len(wallets), "bar": round(b_list, 2),
                                 "n": sum(r["t"] >= b_list for r in scored)},
            "n_t_ge_2": sum(r["t"] >= 2 for r in scored),
            "max_t": max((r["t"] for r in scored), default=None),
            "median_t": sorted(r["t"] for r in scored)[len(scored) // 2] if scored else None,
            "spearman_grade_score_vs_t": None if rho is None else round(rho, 3),
            "n_subaccounts_in_list": sum(r["role"] == "subAccount" for r in rows),
            "masters_shared_by_more_than_one": {k: v for k, v in masters.items() if v > 1},
            "n_with_own_subaccounts": sum(r["n_subaccounts"] > 0 for r in rows),
            "s_wallets": [r for r in rows if r["grade"] == "S"],
        },
        "rows": rows,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("n_list", "n_scored", "excluded", "primary")}, indent=1))
    print(json.dumps({k: v for k, v in res["reported"].items() if k != "s_wallets"}, indent=1))


if __name__ == "__main__":
    main()
