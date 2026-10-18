"""Holdings-based estimates for investors who publish only 13F holdings.

    python tools/build_13f_clones.py --cache .rankcache [--refresh] --out docs/data/ranking/clones.json

A 13F filing lists a manager's long US-listed positions at quarter end. The estimate holds each
quarter's long stock positions, weighted by reported value, from that quarter end to the next, letting
the weights drift with prices inside the quarter, and reads monthly returns from Yahoo Finance
adjusted closes. Options (put/call rows) are left out and their share of reported value is recorded,
because a book that is mostly options is not described by its long stocks. Positions without a price
history are left out too; a quarter whose priced positions cover less than 80% of the long stock
value is skipped. Filings come from 13f.info, which mirrors SEC EDGAR.

This is an estimate of the published long book, not the manager's return: a filing omits shorts,
leverage, cash, non-US positions and trades within the quarter. The page labels it that way.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ranking as br  # noqa: E402

MANAGERS = [  # (id, who, firm, 13f.info manager path)
    ("duan", "Duan Yongping (段永平)", "H&H International", "0001759760-h-h-international-investment-llc"),
    ("burry", "Michael Burry", "Scion Asset Management", "0001649339-scion-asset-management-llc"),
    ("druck", "Stanley Druckenmiller", "Duquesne Family Office", "0001536411-duquesne-family-office-llc"),
    ("lilu", "Li Lu (李录)", "Himalaya Capital", "0001709323-himalaya-capital-management-llc"),
    ("leopold", "Leopold Aschenbrenner", "Situational Awareness LP", "0002045724-situational-awareness-lp"),
    ("tepper", "David Tepper", "Appaloosa", "0001656456-appaloosa-lp"),
    ("klarman", "Seth Klarman", "Baupost Group", "0001061768-baupost-group-llc-ma"),
    ("hillhouse", "Zhang Lei (张磊)", "Hillhouse (HHLR Advisors)", "0001762304-hhlr-advisors-ltd"),
    ("coleman", "Chase Coleman", "Tiger Global", "0001167483-tiger-global-management-llc"),
    ("einhorn", "David Einhorn", "Greenlight Capital", "0001079114-greenlight-capital-inc"),
    ("loeb", "Dan Loeb", "Third Point", "0001040273-third-point-llc"),
    ("pabrai", "Mohnish Pabrai", "Dalal Street", "0001549575-dalal-street-llc"),
    ("akre", "Chuck Akre", "Akre Capital", "0001112520-akre-capital-management-llc"),
    ("gates", "Bill Gates", "Gates Foundation Trust", "0001166559-gates-foundation-trust"),
    ("brk13f", "Warren Buffett", "Berkshire Hathaway, 13F stock portfolio", "0001067983-berkshire-hathaway-inc"),
]
FIRST_QUARTER = "2014-12"  # quarter ends from here on; older filings are sparse on the mirror
MIN_COVER = 0.80
OPTIONS_LIMIT = 0.30


def get(cache, url, name, refresh, as_json=True):
    path = os.path.join(cache, name)
    if refresh or not os.path.exists(path):
        import subprocess
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
        out = subprocess.run(["curl", "-s", "-m", "60", "-A", br.UA, "-o", path, url], env=env)
        if out.returncode != 0:
            raise RuntimeError(f"curl {out.returncode}: {url}")
        time.sleep(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f) if as_json else f.read()


def quarter_end(label):
    """'q2-2026' -> '2026-06'."""
    q, y = label.split("-")
    return f"{y}-{int(q[1]) * 3:02d}"


def filings(cache, path, refresh):
    page = get(cache, f"https://13f.info/manager/{path}", f"13f_mgr_{path[:10]}.html", refresh, as_json=False)
    seen, out = set(), []
    for acc, label in re.findall(r'href="/13f/(\d+)-[a-z0-9-]*?-(q[1-4]-\d{4})"', page):
        qe = quarter_end(label)
        if qe in seen or qe < FIRST_QUARTER:
            continue  # the first link per quarter is the latest filing (amendments included)
        seen.add(qe)
        out.append((qe, acc))
    return sorted(out)


def yahoo_symbol(t):
    return t.replace(".", "-").replace("/", "-")


def months_after(qe, k=3):
    out, m = [], qe
    for _ in range(k):
        m = br._next(m)
        out.append(m)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    bench = br.monthly_returns(br.yahoo_monthly(a.cache, br.BENCH, False)["px"])
    with open(os.path.join(br.ROOT, "docs", "data", "hl", "latest.json"), encoding="utf-8") as f:
        BAR = round(br.hw.bar(json.load(f)["boards"]["pnl"]["ranked_from"]), 2)
    last_month = max(bench)
    px_cache = {}

    def prices(t):
        if t not in px_cache:
            try:
                got = br.yahoo_monthly(a.cache, yahoo_symbol(t), a.refresh)
                px_cache[t] = got["px"] if got and got.get("currency") in (None, "USD") else None
            except Exception as ex:
                print("price", t, ex, file=sys.stderr)
                px_cache[t] = None
        return px_cache[t]

    result = []
    for mid, who, firm, path in MANAGERS:
        if a.only and mid not in a.only:
            continue
        fl = filings(a.cache, path, a.refresh)
        rets, cover, opt_share, skipped = {}, [], [], []
        for qe, acc in fl:
            d = get(a.cache, f"https://13f.info/data/13f/{acc}", f"13f_{acc}.json", a.refresh)["data"]
            stocks = [r for r in d if not r[8] and r[0]]
            total = sum(r[4] or 0 for r in d)
            opts = sum(r[4] or 0 for r in d if r[8])
            opt_share.append(opts / total if total else 0)
            longv = sum(r[4] or 0 for r in stocks)
            w = {}
            for r in stocks:
                w[r[0]] = w.get(r[0], 0) + (r[4] or 0)
            months = [m for m in months_after(qe) if m <= last_month]
            if not months:
                continue
            priced = {t: v for t, v in w.items() if prices(t) and all(m in prices(t) for m in [qe] + months)}
            c = sum(priced.values()) / longv if longv else 0
            cover.append(c)
            if c < MIN_COVER:
                skipped.append(qe)
                continue
            tot = sum(priced.values())
            ww = {t: v / tot for t, v in priced.items()}
            prev = qe
            for m in months:
                r_m = {t: prices(t)[m] / prices(t)[prev] - 1 for t in ww}
                port = sum(ww[t] * r_m[t] for t in ww)
                rets[m] = port
                ww = {t: ww[t] * (1 + r_m[t]) / (1 + port) for t in ww}
                prev = m
        sc = br.score_series(rets, bench, 12)
        mean_opt = sum(opt_share) / len(opt_share) if opt_share else 0
        row = {"id": "f13_" + mid, "group": "clones", "name": firm, "who": who, "venue": f"13F holdings, {len(fl)} quarters",
               "source": f"13f.info (SEC EDGAR mirror), {path}", "benchmark": "S&P 500 with dividends (VFINX)",
               "quarters": len(fl), "quarters_skipped": skipped, "mean_cover": round(sum(cover) / len(cover), 3) if cover else None,
               "options_share_mean": round(mean_opt, 3)}
        if sc and mean_opt <= OPTIONS_LIMIT:
            row.update(sc)
            row["z_10y"] = None
            row["verdict"] = br.grade(sc["z"], BAR)
        else:
            row["error"] = "mostly options" if mean_opt > OPTIONS_LIMIT else "too few priced quarters"
        result.append(row)
        print(f"{mid:10} q={len(fl):3} skipped={len(skipped):2} cover={row['mean_cover']} opt={mean_opt:.2f} "
              f"z={row.get('z')} yrs={row.get('years')} ann={row.get('ann_return')} bench={row.get('ann_bench')}")
    out = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "method": __doc__.strip().split("\n\n", 1)[1], "rows": result}
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
