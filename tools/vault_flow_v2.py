"""Vault flow test, version 2: exact deposits and withdrawals (docs/data/hl/VAULT_FLOW_V2_PREREG.md).

    python tools/vault_flow_v2.py fetch HISTORIES_JSONL VAULTS_JSON OUT_DIR
    python tools/vault_flow_v2.py run OUT_DIR [--out RESULTS_JSON]

`fetch` rebuilds version 1's eligible month-vaults (same rules, same code), writes them to
OUT_DIR/eligible.json, then saves every ledger event of those vaults and of their leaders from
2025-01-01 to 2026-10-31 (`info userNonFundingLedgerUpdates`, paged by startTime) to
OUT_DIR/ledgers/<address>.json. Resumable; paced at about one request a second; proxies bypassed.

`run` computes, for each eligible month-vault, the exact flow over (t, t + 30d]:
  F_all  vault's vaultDeposit usdc - its vaultWithdraw requestedUsd, over account value at t
  F*     F_all without the leader: the leader's deposits into this vault (from the leader's ledger)
         taken off, the leader's withdrawals (user = leader) dropped
then step 1 (pooled Spearman of version 1's F against F_all) and step 2 (version 1's tests with F*,
seed 20261104), and the decision as pre-registered.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vault_flow_test as V  # noqa: E402

API = "https://api.hyperliquid.xyz/info"
START, END = 1735689600000, 1793491200000  # 2025-01-01, 2026-11-01 00:00 UTC
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SEED2 = 20261104
STEP1_BAR = 0.7


def post(body, tries=12):
    for k in range(tries):
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with OPENER.open(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            wait = min(60, 5 * (k + 1))
            print(f"retry {k + 1} in {wait}s: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"gave up: {body}")


def ledger(addr):
    """Every non-funding ledger event of `addr` in [START, END), deduplicated across page edges."""
    out, seen, start = [], set(), START
    while True:
        t0 = time.time()
        page = post({"type": "userNonFundingLedgerUpdates", "user": addr, "startTime": start, "endTime": END})
        time.sleep(max(0.0, 1.05 - (time.time() - t0)))
        new = 0
        for e in page:
            key = (e.get("hash"), e["time"], json.dumps(e["delta"], sort_keys=True))
            if key not in seen:
                seen.add(key)
                out.append(e)
                new += 1
        if len(page) < 2000 or new == 0:
            return out
        start = max(e["time"] for e in page)  # same-millisecond events at the edge are caught by the dedup


def eligible(histories):
    rows = []
    for t in V.month_ends():
        for v in histories:
            o = V.observe(v, t)
            if isinstance(o, dict):
                av = [(int(a), float(b)) for a, b in v["av"]]
                rows.append({"vault": v["vault"], "t": t, "av_t": V.interp(av, t, v["closed"]), **o})
    return rows


def cmd_fetch(a):
    os.makedirs(os.path.join(a.out_dir, "ledgers"), exist_ok=True)
    with open(a.histories, encoding="utf-8") as f:
        hist = [json.loads(line) for line in f if line.strip()]
    rows = eligible(hist)
    leaders = {v["summary"]["vaultAddress"]: v["summary"]["leader"] for v in json.load(open(a.vaults, encoding="utf-8"))}
    for r in rows:
        r["leader"] = leaders[r["vault"]]
    with open(os.path.join(a.out_dir, "eligible.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f)
    addrs = sorted({r["vault"] for r in rows} | {r["leader"] for r in rows})
    print(f"{len(rows)} month-vaults, {len(addrs)} addresses to fetch", flush=True)
    for i, addr in enumerate(addrs):
        p = os.path.join(a.out_dir, "ledgers", addr + ".json")
        if os.path.exists(p):
            continue
        ev = ledger(addr)
        with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(ev, f)
        os.replace(p + ".tmp", p)
        print(f"{i + 1}/{len(addrs)} {addr} {len(ev)}", flush=True)
    print("done", flush=True)


def flows(row, vault_ev, leader_ev):
    t0, t1 = row["t"], row["t"] + 30 * V.DAY
    dep = wd = wd_leader = dep_leader = 0.0
    for e in vault_ev:
        if not (t0 < e["time"] <= t1):
            continue
        d = e["delta"]
        if d["type"] == "vaultDeposit" and d.get("vault") == row["vault"]:
            dep += float(d["usdc"])
        elif d["type"] == "vaultWithdraw" and d.get("vault") == row["vault"]:
            amt = float(d["requestedUsd"])
            wd += amt
            if d.get("user") == row["leader"]:
                wd_leader += amt
    for e in leader_ev:
        d = e["delta"]
        if t0 < e["time"] <= t1 and d["type"] == "vaultDeposit" and d.get("vault") == row["vault"]:
            dep_leader += float(d["usdc"])
    f_all = (dep - wd) / row["av_t"]
    f_star = ((dep - dep_leader) - (wd - wd_leader)) / row["av_t"]
    return f_all, f_star


def cmd_run(a):
    rows = json.load(open(os.path.join(a.out_dir, "eligible.json"), encoding="utf-8"))
    cache = {}

    def ev(addr):
        if addr not in cache:
            p = os.path.join(a.out_dir, "ledgers", addr + ".json")
            cache[addr] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
        return cache[addr]

    done = []
    missing = 0
    for r in rows:
        ve, le = ev(r["vault"]), ev(r["leader"])
        if ve is None or le is None:
            missing += 1
            continue
        r["F_all"], r["F_star"] = flows(r, ve, le)
        done.append(r)
    out = {"month_vaults": len(rows), "with_complete_ledger": len(done), "missing_ledger": missing,
           "theta": V.THETA, "min_obs": V.MIN_OBS, "step1_bar": STEP1_BAR}
    f1 = np.array([r["F"] for r in done])
    fa = np.array([r["F_all"] for r in done])
    out["step1_spearman_F_v1_vs_F_all"] = V.corr(V.ranks(f1), V.ranks(fa)) if len(done) > 2 else None
    months = []
    for t in sorted({r["t"] for r in done}):
        m = [r for r in done if r["t"] == t]
        label = time.strftime("%Y-%m", time.gmtime((t - V.DAY) / 1000))
        if len(m) < V.MIN_MONTH_N:
            months.append({"month": label, "n": len(m), "used": False})
            continue
        F = V.winsor(np.array([r["F_star"] for r in m]))
        R, S, L = (np.array([r[k] for r in m]) for k in "RSL")
        months.append({"month": label, "n": len(m), "used": True, **V.month_stats(F, R, S, L), "_data": (F, R, S, L)})
    used = [m for m in months if m["used"]]
    n_obs = sum(m["n"] for m in used)
    rng = np.random.default_rng(SEED2)
    out["months"] = [{k: v for k, v in m.items() if k != "_data"} for m in months]
    out["observations"] = n_obs
    if used:
        for key in ("rho_FR", "partial_FS_R", "partial_FL_R"):
            vals = [m[key] for m in used]
            out[key] = {"mean": float(np.mean(vals)), "ci95": V.bootstrap(vals, rng)}
        shuf = [np.mean([V.month_stats(*(m["_data"][:2]), rng.permutation(m["_data"][2]), m["_data"][3])["partial_FS_R"]
                         for m in used]) for _ in range(1000)]
        real = out["partial_FS_R"]["mean"]
        out["shuffle_control"] = {"p2.5": float(np.percentile(shuf, 2.5)), "p50": float(np.percentile(shuf, 50)),
                                  "p97.5": float(np.percentile(shuf, 97.5)),
                                  "share_at_or_above_real": float(np.mean(np.array(shuf) >= real))}
    step1_ok = out["step1_spearman_F_v1_vs_F_all"] is not None and out["step1_spearman_F_v1_vs_F_all"] >= STEP1_BAR
    if n_obs < V.MIN_OBS or not used:
        out["decision"] = "underpowered"
    elif out["rho_FR"]["ci95"][0] > 0:
        ok = out["partial_FS_R"]["mean"] >= V.THETA and out["partial_FS_R"]["ci95"][0] > 0
        out["decision"] = "credibility_rewarded" if ok else "not_rewarded"
    elif step1_ok:
        out["decision"] = "not_rewarded_deposits_do_not_follow_performance"
    else:
        out["decision"] = "no_conclusion"
    s = json.dumps(out, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(s)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("histories")
    f.add_argument("vaults")
    f.add_argument("out_dir")
    r = sub.add_parser("run")
    r.add_argument("out_dir")
    r.add_argument("--out")
    a = ap.parse_args()
    cmd_fetch(a) if a.cmd == "fetch" else cmd_run(a)


if __name__ == "__main__":
    main()
