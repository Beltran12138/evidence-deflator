"""What a Hyperliquid vault's depositors actually made, against what its curve shows.

    python tools/vault_follower_gap.py VAULT [VAULT ...] [--out FILE]

The vault's curve is time-weighted: it compounds the vault's return from each depositor's entry to
now, as if one dollar went in at entry and stayed. A depositor's own return is money-weighted: their
all-time PnL in the vault over the money they put in net (vault equity now minus all-time PnL). The
difference is what timing and fees took: adding after a run, withdrawing after a drawdown, and the
leader's profit share. Welton calls the timing part negative investor alpha (Top Traders Unplugged,
2026-10); Morningstar's "Mind the Gap" measures the same thing for mutual funds.

Lower bound, not an estimate: vaultDetails lists only the largest current depositors (up to 100).
Anyone who already withdrew, often after a loss, is missing, so the gap among those listed is the
gentler side of the real one.

Per vault it reports the dollar-weighted depositor return, the dollar-weighted curve return over the
same entry dates, the gap with the leader's profit share taken off the curve (an estimate: the share is
charged on each depositor's own profit), and how many listed depositors did worse than the curve.

First run, 2026-10-18, the 60 largest open vaults by TVL: 28 had a reliable curve and at least 20
listed depositors. After the fee estimate, depositors trailed the curve in 19 of 28; the median gap
was -1.4 points, but -17.7 points weighted by money, because the gap was largest where the curve was
best (Jade Lotus Capital: curve +341%, depositors +185%; Citadel: +333% against +68%). Public endpoint, no key:
info vaultDetails.
"""
import argparse
import json
import urllib.request

API = "https://api.hyperliquid.xyz/info"


def post(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def curve_return(history, pnl, since):
    """Vault return compounded from `since` to the last sample: product of (1 + dPnL / capital).

    Capital is the account value before the interval plus any money deposited during it. Samples are
    sparse, and a deposit landing in the same interval as a loss would otherwise make one interval lose
    more than the account held (a curve below -100%)."""
    g = 1.0
    for (ta, va), (tb, vb) in zip(history, history[1:]):
        if tb <= since or ta not in pnl or tb not in pnl:
            continue
        d = pnl[tb] - pnl[ta]
        cap = va + max((vb - va) - d, 0.0)
        if cap <= 0:
            continue
        frac = (tb - since) / (tb - ta) if ta < since else 1.0  # interval straddles entry: count the part after it
        g *= 1 + frac * d / cap
    return g - 1


def rough_share(history, pnl, since):
    """Share of intervals after `since` in which money moved in or out by more than a quarter of capital.

    The all-time history has about a hundred samples. When large deposits or withdrawals land inside
    those intervals, when the PnL happened relative to them is unknown and the curve can be far off; such
    vaults are reported but marked curve_reliable = False."""
    n = rough = 0
    for (ta, va), (tb, vb) in zip(history, history[1:]):
        if tb <= since or ta not in pnl or tb not in pnl:
            continue
        flow = (vb - va) - (pnl[tb] - pnl[ta])
        cap = va + max(flow, 0.0)
        n += 1
        rough += cap <= 0 or abs(flow) > 0.25 * cap
    return rough / n if n else None


def gap(details):
    pf = dict(details["portfolio"])["allTime"]
    hist = [(int(t), float(v)) for t, v in pf["accountValueHistory"]]
    pnl = {int(t): float(v) for t, v in pf["pnlHistory"]}
    rows = []
    for f in details.get("followers", []):
        if f.get("user") == details.get("leader"):
            continue
        eq, ap = float(f["vaultEquity"]), float(f["allTimePnl"])
        net_in = eq - ap
        if net_in <= 0:  # took out more than they put in; a return on net money in is undefined
            continue
        rows.append({"user": f["user"], "net_in": net_in, "pnl": ap, "own": ap / net_in,
                     "curve": curve_return(hist, pnl, int(f["vaultEntryTime"])), "days": f.get("daysFollowing")})
    if not rows:
        return {"vault": details.get("vaultAddress"), "name": details.get("name"), "listed": 0}
    first = min(int(f["vaultEntryTime"]) for f in details["followers"] if f.get("user") != details.get("leader"))
    rough = rough_share(hist, pnl, first)
    w = sum(r["net_in"] for r in rows)
    own = sum(r["pnl"] for r in rows) / w
    curve = sum(r["net_in"] * r["curve"] for r in rows) / w
    return {"vault": details.get("vaultAddress"), "name": details.get("name"),
            "leader_commission": details.get("leaderCommission"), "listed": len(rows),
            "net_in_listed": round(w, 2), "depositor_return_dollar_weighted": round(own, 4),
            "curve_return_same_entries": round(curve, 4), "gap": round(own - curve, 4),
            # The leader takes a share of depositors' profit; taking it off the curve leaves mostly timing.
            "gap_after_fee_estimate": round(own - (curve * (1 - float(details.get("leaderCommission") or 0))
                                                   if curve > 0 else curve), 4),
            "worse_than_curve": sum(r["own"] < r["curve"] for r in rows),
            "rough_interval_share": None if rough is None else round(rough, 3),
            "curve_reliable": rough is not None and rough <= 0.10}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vaults", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = [gap(post({"type": "vaultDetails", "vaultAddress": v.lower()})) for v in a.vaults]
    s = json.dumps(out, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(s)


if __name__ == "__main__":
    main()
