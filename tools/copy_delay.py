"""What copying a Hyperliquid wallet late would have cost: each fill redone `delay` minutes later.

    python tools/copy_delay.py ADDRESS [--days 45] [--delays 15,60,240] [--out FILE]

A copier who mirrors every fill of the wallet, `delay` minutes after it, pays the price move over that
delay on every fill: for a buy, size x (price at t + delay - fill price); for a sell, the opposite. The
sum over the window is the delay cost, reported against the wallet's own realised PnL over the same
fills (closedPnl minus fees). A cost near or above the realised PnL means the record cannot be copied
at that speed, however strong it looks.

Prices come from 15-minute candles (Hyperliquid keeps about 52 days of them; 1-minute candles only
about 3.5 days). The price at t + delay is interpolated linearly between the open and close of the
candle containing it, so delays shorter than 15 minutes are not measured. Fills on coins without
candles (most spot pairs) are skipped and counted. Hyperliquid serves only a wallet's most recent
~10,000 fills, so for an active wallet the window starts at first_fill_ms, not --days ago. Same-size copying is assumed: a copier at a
different size scales cost and PnL together, so the ratio does not change.

Public endpoints, no key: info userFillsByTime (paged, 2,000 per call) and candleSnapshot.
Prompted by Welton's point that a strategy losing much of its P&L when executed fifteen minutes late
has a different capacity and robustness from one that survives a day's delay (Top Traders Unplugged,
2026-10).
"""
import argparse
import bisect
import json
import time
import urllib.request

API = "https://api.hyperliquid.xyz/info"
CANDLE_MS = 15 * 60 * 1000


def post(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fills(address, start, end):
    out = []
    while start < end:
        page = post({"type": "userFillsByTime", "user": address, "startTime": start, "endTime": end,
                     "aggregateByTime": True})
        if not page:
            break
        out += page
        if len(page) < 2000:
            break
        start = max(int(f["time"]) for f in page) + 1
        time.sleep(0.2)
    return out


def candles(coin, start, end):
    for attempt in range(3):  # many coins in a row trip the rate limit; back off and retry
        try:
            cs = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": "15m", "startTime": start,
                                                          "endTime": end}})
            time.sleep(0.15)
            return sorted((int(c["t"]), float(c["o"]), float(c["c"])) for c in cs)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return []


def price_at(cs, ms):
    """Linear between open and close of the 15-minute candle containing ms; None outside the candles."""
    starts = [c[0] for c in cs]
    i = bisect.bisect_right(starts, ms) - 1
    if i < 0 or ms >= cs[i][0] + CANDLE_MS:
        return None
    t, o, c = cs[i]
    return o + (c - o) * (ms - t) / CANDLE_MS


def delay_cost(fs, cs_by_coin, delay_min):
    """Sum over fills of signed size x (price delay_min later - fill price); fills without a price are skipped."""
    cost, used, skipped = 0.0, 0, 0
    for f in fs:
        cs = cs_by_coin.get(f["coin"]) or []
        p = price_at(cs, int(f["time"]) + delay_min * 60000) if cs else None
        if p is None:
            skipped += 1
            continue
        sign = 1 if f["side"] == "B" else -1
        cost += sign * float(f["sz"]) * (p - float(f["px"]))
        used += 1
    return cost, used, skipped


def run(address, days=45, delays=(15, 60, 240)):
    end = int(time.time() * 1000)
    start = end - days * 86400000
    fs = fills(address, start, end)
    coins = sorted({f["coin"] for f in fs})
    cs_by_coin = {c: candles(c, start - CANDLE_MS, end) for c in coins}
    # Hyperliquid serves only the most recent ~10,000 fills, so an active wallet's window starts later than asked.
    out = {"address": address, "from_ms": start, "to_ms": end, "fills": len(fs), "coins": len(coins),
           "first_fill_ms": min((int(f["time"]) for f in fs), default=None),
           "coins_without_candles": sum(1 for c in coins if not cs_by_coin[c])}
    rows = []
    for d in delays:
        cost, used, skipped = delay_cost(fs, cs_by_coin, d)
        priced = [f for f in fs if (cs_by_coin.get(f["coin"]) or []) and
                  price_at(cs_by_coin[f["coin"]], int(f["time"]) + d * 60000) is not None]
        realised = sum(float(f["closedPnl"]) - float(f.get("fee") or 0) for f in priced)
        rows.append({"delay_min": d, "fills_priced": used, "fills_skipped": skipped,
                     "realised_pnl_priced_fills": round(realised, 2), "delay_cost": round(cost, 2),
                     "cost_share_of_pnl": (round(cost / realised, 3) if realised > 0 else None)})
    out["delays"] = rows
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address")
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--delays", default="15,60,240")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = run(a.address.lower(), a.days, tuple(int(x) for x in a.delays.split(",")))
    s = json.dumps(r, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(s)


if __name__ == "__main__":
    main()
