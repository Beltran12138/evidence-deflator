"""Evidence Ranking: famous public records and the strongest crypto records, on one ruler.

    python tools/build_ranking.py --cache .rankcache [--refresh] --out docs/data/ranking/latest.json

Every record is scored on its excess over a market: stocks and funds against the S&P 500 with
dividends (Vanguard 500 Index, VFINX, adjusted close), wallets against BTC, Polymarket against the
price paid for each share (which is already a market-relative test). A raw-return test would credit a
record for the market rising: the S&P 500 itself reaches z = 4.94 against zero over 1965-2025
(tools/masters_calibration.py).

Stocks and funds: monthly total returns from Yahoo Finance's chart endpoint (daily adjusted close,
last value of each month), converted to USD where needed. The t of alpha in an OLS of the record's
monthly return on the benchmark's is put on the normal scale with n - 2 degrees of freedom (the same
Student-t mapping as the wallet check). Berkshire Hathaway and Renaissance Medallion use yearly
returns from their primary sources instead (the 2025 shareholder letter; Cornell 2019, Table 1, from
Zuckerman 2019), which are longer than any price feed.

Only funds that exist today are in a price feed, so the ranking leans toward survivors; that is
stated on the page. Each record's verdict uses the same bar as a wallet picked from the Hyperliquid
board (bar(47,000) = 4.90): famous records are famous because they were picked after the fact.
"""
import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402

NOW = int(time.time())
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

# Yearly returns from primary sources (percent). Berkshire: per-share market value and S&P 500 with
# dividends, 2025 letter table (1965 and 1966 years ended 9/30; 1967 is 15 months). Medallion: net of
# fees, Cornell (2019) Table 1.
BRK_YEARS = list(range(1965, 2026))
BRK = [49.5, -3.4, 13.3, 77.8, 19.4, -4.6, 80.5, 8.1, -2.5, -48.7, 2.5, 129.3, 46.8, 14.5, 102.5, 32.8, 31.8, 38.4, 69.0, -2.7,
       93.7, 14.2, 4.6, 59.3, 84.6, -23.1, 35.6, 29.8, 38.9, 25.0, 57.4, 6.2, 34.9, 52.2, -19.9, 26.6, 6.5, -3.8, 15.8, 4.3,
       0.8, 24.1, 28.7, -31.8, 2.7, 21.4, -4.7, 16.8, 32.7, 27.0, -12.5, 23.4, 21.9, 2.8, 11.0, 2.4, 29.6, 4.0, 15.8, 25.5, 10.9]
SPX = [10.0, -11.7, 30.9, 11.0, -8.4, 3.9, 14.6, 18.9, -14.8, -26.4, 37.2, 23.6, -7.4, 6.4, 18.2, 32.3, -5.0, 21.4, 22.4, 6.1,
       31.6, 18.6, 5.1, 16.6, 31.7, -3.1, 30.5, 7.6, 10.1, 1.3, 37.6, 23.0, 33.4, 28.6, 21.0, -9.1, -11.9, -22.1, 28.7, 10.9,
       4.9, 15.8, 5.5, -37.0, 26.5, 15.1, 2.1, 16.0, 32.4, 13.7, 1.4, 12.0, 21.8, -4.4, 31.5, 18.4, 28.7, -18.1, 26.3, 25.0, 17.9]
MED_YEARS = list(range(1988, 2019))
MED_NET = [9.04, -3.20, 58.24, 39.44, 33.60, 39.12, 70.72, 38.32, 31.52, 21.20, 41.68, 24.48, 98.48, 33.02, 25.82, 21.90,
           24.92, 29.51, 44.30, 73.42, 82.38, 38.98, 29.40, 37.02, 29.01, 46.93, 39.20, 36.01, 35.62, 45.02, 39.98]

# Records with a public price history. window: (first month, last month) of a manager's tenure where it
# is well documented; otherwise the whole history the feed has. fx: Yahoo FX ticker to convert to USD.
# Yahoo's mutual-fund prices before 1987 miss distributions (VFINX is 2-9 points a year below the S&P 500
# with dividends in 1981-86, FMAGX shows -21% for 1981), so every feed starts in 1988; main() checks
# VFINX against the letter's S&P 500 column for 1988 onward. That leaves Peter Lynch's Magellan years
# (1977-1990) and John Neff's Windsor years (1964-1995) without a usable monthly series: listed as needing data.
FEED_FLOOR = "1988-01"
NEEDS_DATA = [
    ("Peter Lynch", "Fidelity Magellan, 1977–1990", "the price feed misses distributions before 1987; needs Fidelity’s yearly returns"),
    ("John Neff", "Vanguard Windsor, 1964–1995", "same gap in the price feed; needs Vanguard’s yearly returns"),
    ("George Soros", "Quantum Fund", "no complete yearly series published; only scattered years"),
    ("Peter Thiel", "Clarium Capital, Founders Fund", "no public return series"),
    ("Leopold Aschenbrenner", "Situational Awareness LP", "most of the 13F value is options, which a holdings estimate cannot price; returns reported by the press, not published"),
    ("Ray Dalio", "Bridgewater Pure Alpha", "private; the public All Weather ETF is too new"),
]
PRICED = [
    dict(id="sequx", name="Sequoia Fund", who="Ruane, Cunniff", tickers=["SEQUX"]),
    dict(id="lmvtx", name="Legg Mason Value Trust (now ClearBridge)", who="Bill Miller (founding manager)", tickers=["LMVTX"]),
    dict(id="dodgx", name="Dodge & Cox Stock", who="Dodge & Cox", tickers=["DODGX"]),
    dict(id="fairx", name="Fairholme Fund", who="Bruce Berkowitz", tickers=["FAIRX"]),
    dict(id="arkk", name="ARK Innovation ETF", who="Cathie Wood", tickers=["ARKK"]),
    dict(id="psh", name="Pershing Square Holdings", who="Bill Ackman", tickers=["PSHD.L", "PSH.L"], fx_by_currency=True),
    dict(id="smt", name="Scottish Mortgage", who="Baillie Gifford", tickers=["SMT.L"], fx_by_currency=True),
    dict(id="mkl", name="Markel Group", who="Tom Gayner", tickers=["MKL"]),
    dict(id="ffh", name="Fairfax Financial", who="Prem Watsa", tickers=["FFH.TO"], fx_by_currency=True),
    dict(id="djco", name="Daily Journal Corp.", who="Charlie Munger (chairman to 2022)", tickers=["DJCO"]),
    dict(id="nanc", name="NANC ETF (Democrats’ disclosed trades)", who="Nancy Pelosi and colleagues, as disclosed", tickers=["NANC"]),
    dict(id="brk_monthly", name="Berkshire Hathaway, monthly prices", who="Warren Buffett", tickers=["BRK-A"], cross_check=True),
]
# Chinese public funds: daily returns from Eastmoney (fund.eastmoney.com/pingzhongdata/<code>.js,
# equityReturn, which includes distributions), compounded to month ends. Benchmark: Harvest CSI 300
# index fund (160706), whose returns include the index's dividends, less about 0.6% a year in fees.
# window: the named manager's tenure on this fund where it starts at the fund's launch or is well known.
CN = [
    dict(id="cn_161005", code="161005", name="富国天惠成长 (Fullgoal Tianhui Growth)", who="Zhu Shaoxing (朱少醒), since launch"),
    dict(id="cn_110011", code="110011", name="易方达优质精选 (E Fund Quality Select)", who="Zhang Kun (张坤)", window=("2012-10", None),
         note="Zhang Kun from September 2012; the fund later became a QDII fund with overseas holdings."),
    dict(id="cn_005827", code="005827", name="易方达蓝筹精选 (E Fund Blue Chip Select)", who="Zhang Kun (张坤), since launch"),
    dict(id="cn_003095", code="003095", name="中欧医疗健康 (China Europe Healthcare)", who="Ge Lan (葛兰), since launch"),
    dict(id="cn_163406", code="163406", name="兴全合润 (Aegon-Industrial Herun)", who="Xie Zhiyu (谢治宇), current manager",
         note="Whole fund history since 2010; the current manager joined later."),
    dict(id="cn_260108", code="260108", name="景顺长城新兴成长 (Invesco Great Wall Emerging Growth)", who="Liu Yanchun (刘彦春), current manager",
         note="Whole fund history since 2006; the current manager joined later."),
]
CN_BENCH = "160706"
FX = {"GBp": ("GBPUSD=X", 0.01), "GBP": ("GBPUSD=X", 1.0), "CAD": ("CADUSD=X", 1.0), "USD": (None, 1.0)}
BENCH = "VFINX"


def curl_json(url, path, refresh):
    if refresh or not os.path.exists(path):
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
        out = subprocess.run(["curl", "-s", "-m", "60", "-A", UA, "-o", path, url], env=env)
        if out.returncode != 0:
            raise RuntimeError(f"curl {out.returncode}: {url}")
        time.sleep(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def yahoo_monthly(cache, ticker, refresh):
    """{YYYY-MM: last adjusted close of the month}, currency, first trade date. Drops the current month."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1=0&period2={NOW}"
           f"&interval=1d&events=div%2Csplit%2CcapitalGains&includeAdjustedClose=true")
    d = curl_json(url, os.path.join(cache, f"yahoo_{ticker}.json"), refresh)
    res = (d.get("chart") or {}).get("result")
    if not res:
        return None
    r = res[0]
    ts, adj = r.get("timestamp") or [], ((r["indicators"].get("adjclose") or [{}])[0].get("adjclose") or [])
    m = {}
    for t, a in zip(ts, adj):
        if a is None or a <= 0:
            continue
        m[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")] = a
    this = datetime.now(timezone.utc).strftime("%Y-%m")
    m.pop(this, None)
    return {"px": m, "currency": r["meta"].get("currency"), "symbol": r["meta"].get("symbol")}


def eastmoney_monthly(cache, code, refresh):
    """{YYYY-MM: total-return index at month end} from Eastmoney's daily equityReturn (percent)."""
    path = os.path.join(cache, f"em_{code}.js")
    if refresh or not os.path.exists(path):
        out = subprocess.run(["curl", "-s", "-m", "60", "-L", "--noproxy", "*", "-A", UA, "-e", "https://fund.eastmoney.com/",
                              "-o", path, f"https://fund.eastmoney.com/pingzhongdata/{code}.js"])
        if out.returncode != 0:
            raise RuntimeError(f"curl {out.returncode}: eastmoney {code}")
        time.sleep(1)
    with open(path, encoding="utf-8") as f:
        s = f.read()
    i = s.index("Data_netWorthTrend =") + len("Data_netWorthTrend =")
    nw = json.JSONDecoder().raw_decode(s.lstrip()[0:0] + s[i:].lstrip())[0]
    idx, m = 1.0, {}
    for p in nw:
        r = p.get("equityReturn")
        idx *= 1 + (float(r) / 100 if r not in (None, "") else 0.0)
        m[datetime.fromtimestamp(p["x"] / 1000, timezone.utc).strftime("%Y-%m")] = idx
    m.pop(datetime.now(timezone.utc).strftime("%Y-%m"), None)
    return m


def monthly_returns(px):
    ks = sorted(px)
    return {b: px[b] / px[a] - 1 for a, b in zip(ks, ks[1:]) if _next(a) == b}


def _next(m):
    y, mo = int(m[:4]), int(m[5:])
    return f"{y + (mo == 12)}-{1 if mo == 12 else mo + 1:02d}"


def alpha_z(y, x):
    """OLS y = a + b x; t of a on the normal scale (n - 2 dof). Returns z, beta, n, a per period."""
    n = len(y)
    if n < 8:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx <= 0:
        return None
    b = sum((u - mx) * (v - my) for u, v in zip(x, y)) / sxx
    a = my - b * mx
    rss = sum((v - a - b * u) ** 2 for u, v in zip(x, y))
    s2 = rss / (n - 2)
    se = math.sqrt(s2 * (1 / n + mx * mx / sxx))
    t = a / se if se > 0 else float("inf")
    return {"z": round(hw.t_to_z(t, n - 2), 2), "beta": round(b, 2), "n": n, "alpha_per_period": a}


def score_series(rets, bench, periods_per_year, window=None, floor=None):
    ks = sorted(k for k in rets if k in bench and (window is None or window[0] <= k <= window[1]) and (floor is None or k >= floor))
    if len(ks) < 8:
        return None
    y, x = [rets[k] for k in ks], [bench[k] for k in ks]
    out = alpha_z(y, x)
    if not out:
        return None
    yrs = len(ks) / periods_per_year
    ann = (math.prod(1 + v for v in y) ** (1 / yrs) - 1)
    annb = (math.prod(1 + v for v in x) ** (1 / yrs) - 1)
    out.update({"first": ks[0], "last": ks[-1], "years": round(yrs, 1), "ann_return": round(ann, 4),
                "ann_bench": round(annb, 4), "alpha_ann": round(out.pop("alpha_per_period") * periods_per_year, 4)})
    return out


def last_years(rets, bench, periods_per_year, years=10):
    ks = sorted(k for k in rets if k in bench)
    if len(ks) < years * periods_per_year:
        return None
    w = (ks[-years * periods_per_year], ks[-1])
    return score_series(rets, bench, periods_per_year, w)


def grade(z, bar):
    if z is None:
        return "too_short"
    return "clears_board" if z >= bar else "clears_single" if z >= 2 else "loses" if z <= -2 else "luck"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    with open(os.path.join(ROOT, "docs", "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    N_HL = hl["boards"]["pnl"]["ranked_from"]
    BAR = round(hw.bar(N_HL), 2)
    rows, checks = [], {}

    # benchmark, monthly
    b = yahoo_monthly(a.cache, BENCH, a.refresh)
    bench_m = monthly_returns(b["px"])
    off = []
    for y in range(int(FEED_FLOOR[:4]), 2026):
        if f"{y}-12" in b["px"] and f"{y - 1}-12" in b["px"]:
            d = 100 * (b["px"][f"{y}-12"] / b["px"][f"{y - 1}-12"] - 1) - SPX[BRK_YEARS.index(y)]
            off.append(abs(d))
    checks["vfinx_vs_letter_sp500"] = {"years": len(off), "max_abs_diff_pp": round(max(off), 2), "mean_abs_diff_pp": round(statistics.fmean(off), 2)}
    fx_cache = {}

    def fx(currency):
        tk, scale = FX.get(currency, (None, 1.0))
        if tk is None:
            return None
        if tk not in fx_cache:
            fx_cache[tk] = yahoo_monthly(a.cache, tk, a.refresh)["px"]
        return fx_cache[tk], scale

    # yearly primary-source records
    by = {y: r / 100 for y, r in zip(BRK_YEARS, BRK)}
    bs = {y: r / 100 for y, r in zip(BRK_YEARS, SPX)}
    for rid, name, who, series, window, src in [
        ("brk", "Berkshire Hathaway", "Warren Buffett", by, None, "Berkshire 2025 shareholder letter, per-share market value"),
        ("brk_2001", "Berkshire Hathaway, 2001 onward", "Warren Buffett", by, (2001, 2025), "Berkshire 2025 shareholder letter"),
        ("medallion", "Renaissance Medallion, net of fees", "Jim Simons", {y: r / 100 for y, r in zip(MED_YEARS, MED_NET)}, None,
         "Cornell (2019) Table 1, from Zuckerman (2019); estimates, not audited"),
    ]:
        ks = [k for k in sorted(series) if k in bs and (window is None or window[0] <= k <= window[1])]
        sc = score_series({str(k): series[k] for k in ks}, {str(k): bs[k] for k in ks}, 1)
        z10 = None if window or len(ks) < 20 else last_years({str(k): series[k] for k in ks}, {str(k): bs[k] for k in ks}, 1)
        rows.append({"id": rid, "group": "markets", "name": name, "who": who, "venue": "Yearly returns",
                     "source": src, "benchmark": "S&P 500 with dividends", **sc, "z_10y": z10 and z10["z"], "verdict": grade(sc["z"], BAR)})

    for spec in PRICED:
        got = None
        for tk in spec["tickers"]:
            got = yahoo_monthly(a.cache, tk, a.refresh)
            if got and len(got["px"]) > 24:
                break
        if not got:
            rows.append({"id": spec["id"], "group": "markets", "name": spec["name"], "who": spec["who"], "error": "no price history"})
            continue
        px = dict(got["px"])
        cur = got["currency"]
        if spec.get("fx_by_currency") and cur != "USD":
            f = fx(cur)
            if f:
                rate, scale = f
                px = {k: v * scale * rate[k] for k, v in px.items() if k in rate}
        rets = monthly_returns(px)
        if spec.get("cross_check"):
            # yearly price change from the feed against the letter table, as a check on the pipeline
            yr = {}
            for y in range(1981, 2026):
                if f"{y}-12" in got["px"] and f"{y - 1}-12" in got["px"]:
                    yr[y] = got["px"][f"{y}-12"] / got["px"][f"{y - 1}-12"] - 1
            diffs = [abs(yr[y] - by[y]) for y in yr]
            checks["brk_feed_vs_letter"] = {"years": len(diffs), "max_abs_diff_pp": round(100 * max(diffs), 2),
                                            "mean_abs_diff_pp": round(100 * statistics.fmean(diffs), 2)}
            continue
        sc = score_series(rets, bench_m, 12, spec.get("window"), FEED_FLOOR)
        if not sc:
            rows.append({"id": spec["id"], "group": "markets", "name": spec["name"], "who": spec["who"], "error": "too short"})
            continue
        z10 = None if spec.get("window") else last_years(rets, bench_m, 12)
        rows.append({"id": spec["id"], "group": "markets", "name": spec["name"], "who": spec["who"],
                     "venue": f"{got['symbol']}, monthly", "source": f"Yahoo Finance adjusted close ({got['symbol']}, {cur}{' to USD' if cur != 'USD' and spec.get('fx_by_currency') else ''})",
                     "benchmark": "S&P 500 with dividends (VFINX)", "note": spec.get("note"), **sc,
                     "z_10y": z10 and z10["z"], "verdict": grade(sc["z"], BAR)})

    # Chinese public funds against the CSI 300 index fund
    cnb = monthly_returns(eastmoney_monthly(a.cache, CN_BENCH, a.refresh))
    for spec in CN:
        rets = monthly_returns(eastmoney_monthly(a.cache, spec["code"], a.refresh))
        w = spec.get("window")
        win = (w[0], w[1] or "9999-12") if w else None
        sc = score_series(rets, cnb, 12, win)
        if not sc:
            continue
        z10 = None if w else last_years(rets, cnb, 12)
        rows.append({"id": spec["id"], "group": "china", "name": spec["name"], "who": spec["who"], "venue": f"Fund {spec['code']}, monthly",
                     "source": f"Eastmoney daily returns ({spec['code']})", "benchmark": "CSI 300 index fund (160706)", "note": spec.get("note"),
                     **sc, "z_10y": z10 and z10["z"], "verdict": grade(sc["z"], BAR)})

    # crypto: Hyperliquid's strongest records against BTC (from the daily board)
    seen = set()
    hlrows = []
    for key in ("pnl", "roi30"):
        for r in hl["boards"][key]["rows"]:
            if r.get("t_btc") is None or r["address"] in seen:
                continue
            seen.add(r["address"])
            hlrows.append((key, r))
    hlrows.sort(key=lambda kr: -kr[1]["t_btc"])
    for key, r in hlrows[:8]:
        nm = r.get("vault") or r.get("display") or (r["address"][:6] + "…" + r["address"][-4:])
        rows.append({"id": "hl_" + r["address"][2:10], "group": "crypto", "name": nm, "who": None, "address": r["address"],
                     "venue": f"Hyperliquid, #{r['rank']} by {'all-time PnL' if key == 'pnl' else '30-day ROI'}",
                     "source": "Hyperliquid public API, weekly", "benchmark": "BTC", "z": r["t_btc"], "z_raw": r["t"],
                     "beta": r.get("beta_btc"), "years": round(r["weeks"] / 52, 1), "first": r.get("history_from"),
                     "flags": r["flags"], "verdict": grade(r["t_btc"], BAR)})

    # named wallets, scored now
    named = [("machi", "Machi Big Brother", "Jeffrey Huang", "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
              "address labelled machibigbrother.eth (ENS)"),
             ("wynn", "James Wynn", "James Wynn", "0x5078c2fbea2b2ad61bc840bc023e35fce56bedb6",
              "address attributed by Lookonchain and Onchain Lens")]
    try:
        candles = hw.fetch_candles("BTC")
    except Exception:
        candles = []
    for rid, name, who, addr, src in named:
        try:
            c = hw.check(addr, picked_from=N_HL, candles=candles)
            rows.append({"id": rid, "group": "crypto", "name": name, "who": who, "address": addr, "venue": "Hyperliquid",
                         "source": "Hyperliquid public API, weekly; " + src, "benchmark": "BTC", "z": c["t_btc"], "z_raw": c["t"],
                         "beta": c["beta_btc"], "years": round((c["weeks"] or 0) / 52, 1), "first": c["history_from"],
                         "flags": c["flags"], "verdict": grade(c["t_btc"], BAR)})
        except Exception as ex:
            print("named", rid, ex, file=sys.stderr)

    # Polymarket: z against the price paid, events clustered (audit 008)
    pm_path = os.path.join(ROOT, "docs", "data", "cex", "polymarket-2026-10-15.json")
    with open(pm_path, encoding="utf-8") as f:
        pm = json.load(f)
    pmr = sorted([r for r in pm["rows"] if r.get("complete") and r.get("z_cluster") is not None], key=lambda r: -r["z_cluster"])
    keep = pmr[:5] + [r for r in pmr if r["name"] == "Theo4" and r not in pmr[:5]]
    for r in keep:
        rows.append({"id": "pm_" + r["wallet"][2:10], "group": "crypto", "name": r["name"] if len(r["name"]) < 30 else r["wallet"][:6] + "…" + r["wallet"][-4:],
                     "who": "Théo, the 2024 “French whale” (one of his four accounts)" if r["name"] == "Theo4" else None,
                     "address": r["wallet"], "venue": f"Polymarket, #{r['rank']} by all-time profit", "events": r["events"],
                     "source": "Polymarket public API, 2026-10-15 (audit 008)", "benchmark": "price paid per share",
                     "z": r["z_cluster"], "z_raw": None, "beta": None, "years": None, "flags": [],
                     "verdict": grade(r["z_cluster"], BAR)})

    # AI trading agents: Recall's perps competitions (audit 011) and Alpha Arena season 1 (audit 006).
    # Records of days, scored on raw returns: over 4-7 days a market adjustment is smaller than the noise.
    with open(os.path.join(ROOT, "docs", "data", "recall", "recall-2026-10-17.json"), encoding="utf-8") as f:
        rc = json.load(f)
    ags = sorted(((a, c) for c in rc["competitions"] for a in c["agents_detail"] if a["t"] is not None), key=lambda ac: -ac[0]["t"])
    for a_, c in ags[:3]:
        rows.append({"id": "ai_" + a_["agent"][:8], "group": "ai", "name": a_["name"], "who": "AI agent",
                     "venue": f"Recall, {c['name']} ({c['days']} days, {c['agents']} agents)", "source": "Recall public API (audit 011)",
                     "benchmark": "none (raw returns, days long)", "z": a_["t"], "z_raw": a_["t"], "beta": None,
                     "years": None, "flags": [], "verdict": grade(a_["t"], BAR)})
    rows.append({"id": "ai_alpha_arena", "group": "ai", "name": "Best model in Alpha Arena season 1", "who": "AI model (6 competed)",
                 "venue": "nof1 Alpha Arena, season 1", "source": "audit 006", "benchmark": "none (raw returns)", "z": 0.54, "z_raw": 0.54,
                 "beta": None, "years": None, "flags": [], "verdict": grade(0.54, BAR)})

    # holdings-based estimates (tools/build_13f_clones.py), labelled as estimates
    cp = os.path.join(ROOT, "docs", "data", "ranking", "clones.json")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            for r in json.load(f)["rows"]:
                if r.get("z") is not None:
                    r["verdict"] = grade(r["z"], BAR)
                rows.append(r)

    out = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "bar": BAR, "bar_n": N_HL,
        "method": __doc__.strip().split("\n\n", 1)[1],
        "checks": checks,
        "rows": rows,
        "needs_data": [{"who": w, "record": r, "why": y} for w, r, y in NEEDS_DATA],
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out, indent=1, ensure_ascii=False))
    for r in sorted((r for r in rows if r.get("z") is not None), key=lambda r: -r["z"]):
        print(f"{r['z']:6.2f}  {r.get('years') or '':>5}  {r['group']:8} {r['name'][:46]:46} {r.get('first', '')}–{r.get('last', '')}")
    for r in rows:
        if r.get("error"):
            print("ERROR", r["id"], r["error"])
    print("checks", checks)


if __name__ == "__main__":
    main()
