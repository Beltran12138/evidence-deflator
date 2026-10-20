"""Audit 013: TradeRank's LLM trading arena, scored for luck, with Jev (TypeSafe's decision model) in it.

Usage:
    python tools/audit_traderank.py OUT.json [--cache DIR]

TradeRank (traderank.ai) runs month-long seasons in which 9 to 22 AI models each trade $10,000 of
simulated capital in the same 60 assets (10 cryptocurrencies, 50 US large caps), one decision a
day at 16:00 UTC. Everything here is public, no key:

  www.traderank.ai/data/competitions/index.json                 every season: dates, field size, winner, trades
  www.traderank.ai/data/competitions/{season}/reports/index.json  dates of the daily reports, where published
  www.traderank.ai/data/competitions/{season}/reports/daily/{d}.json  standings (cumulative return %) that day
  api.traderank.ai/api/arena/equities                           the running season: each model's equity at every cycle close
  api.traderank.ai/api/arena/models/jev                         Jev's running record (trades, positions)

Returns between consecutive observations (interval in weeks) go through hl_wallet.score, the
estimator behind evidencedeflator.com/wallet/. The bar for the best of a season's field is
Bonferroni, one-sided, as in audits 006 and 011. Archived seasons are scored only where at least 20
daily reports are published; the archive has gaps, so those seasons use the reports' cumulative
returns, with the interval set by the report dates.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

WWW = "https://www.traderank.ai"
API = "https://api.traderank.ai/api/arena"
DAY_W = 1 / 7
MIN_REPORTS = 20


def get(url, cache):
    fn = os.path.join(cache, url.split("//", 1)[1].replace("/", "_") + ("" if url.endswith(".json") else ".json")) if cache else None
    if fn and os.path.exists(fn):
        with open(fn, encoding="utf-8") as f:
            return json.load(f)
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    out = subprocess.run(["curl", "-s", "-m", "60", "-A", "Mozilla/5.0", url], capture_output=True, env=env, check=True).stdout
    try:
        data = json.loads(out)
    except ValueError:  # the site answers a missing file with its HTML shell
        data = None
    if fn:
        os.makedirs(cache, exist_ok=True)
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f)
    time.sleep(0.3)
    return data


def rets_from_values(points):
    """[(t_ms, value)] -> [(return, weeks)]."""
    points = sorted(points)
    return [((b - a) / a, (tb - ta) / 86400000 * DAY_W) for (ta, a), (tb, b) in zip(points, points[1:]) if a > 0]


def scored_field(series, n):
    """series: {model: [(t_ms, value)]}; returns per-model scores and the field summary."""
    bar = H.bar(n) if n > 1 else 2.0
    rows = []
    for mid, pts in series.items():
        sc = H.score(rets_from_values(pts))
        first, last = sorted(pts)[0][1], sorted(pts)[-1][1]
        rows.append({"model": mid, "return_pct": round((last / first - 1) * 100, 2), "t": sc["t"], "sharpe": sc["sharpe"],
                     "observations": len(pts)})
    rows.sort(key=lambda r: -r["return_pct"])
    ts_ = [r["t"] for r in rows if r["t"] is not None]
    return {"field": n, "bar_best_of_n": round(bar, 2), "scored": len(ts_), "t_ge_2": sum(t >= 2 for t in ts_),
            "t_ge_bar": sum(t >= bar for t in ts_), "max_t": max(ts_) if ts_ else None, "models": rows}


def day_ms(d):
    return int(datetime.fromisoformat(d).replace(hour=16, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()

    seasons = get(WWW + "/data/competitions/index.json", a.cache)
    archive = []
    for s in sorted(seasons, key=lambda s: s["startDate"]):
        w, st = s.get("winner") or {}, s.get("stats") or {}
        days, n = s.get("durationDays"), st.get("modelCount")
        row = {"season": s["slug"], "start": s["startDate"], "end": s["endDate"], "days": days, "models": n,
               "winner": w.get("modelName"), "winner_return_pct": None if w.get("returnPct") is None else round(w["returnPct"], 2),
               "winner_trades": w.get("totalTrades"), "trades_all_models": st.get("totalTrades"),
               "trades_per_model": round(st["totalTrades"] / n, 1) if n and st.get("totalTrades") is not None else None,
               "sharpe_needed_for_bar": round(H.bar(n) / (days / 365.25) ** 0.5, 1) if n and days else None}
        idx = get(f"{WWW}/data/competitions/{s['slug']}/reports/index.json", a.cache)
        dates = (idx or {}).get("daily") or []
        row["daily_reports"] = len(dates)
        if len(dates) >= MIN_REPORTS:
            series = {}
            for d in dates:
                rep = get(f"{WWW}/data/competitions/{s['slug']}/reports/daily/{d}.json", a.cache) or {}
                for x in rep.get("standings") or []:
                    series.setdefault(x["modelId"], [(day_ms(s["startDate"]), 10000.0)]).append((day_ms(d), 10000.0 * (1 + x["returnPct"] / 100)))
            row["scored_from_reports"] = scored_field(series, n or len(series))
        archive.append(row)

    comp = get(API + "/competition", a.cache)
    eq = get(API + "/equities", a.cache)["equities"]
    live = scored_field({m: [(p["timestamp"], p["value"]) for p in v["data"]] for m, v in eq.items()}, len(eq))
    live.update({"season": comp.get("id"), "name": comp.get("name"), "days_elapsed": comp.get("daysElapsed"),
                 "days_total": round((comp["endDate"] - comp["startDate"]) / 86400000) if comp.get("endDate") else None})
    jev = get(API + "/models/jev", a.cache)

    out = {"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": [WWW + "/data/competitions/", API],
           "archive": archive, "running_season": live,
           "jev_running": {k: jev.get(k) for k in ("rank", "totalModels", "equity")} | {"metrics": jev.get("metrics"), "vsBenchmark": jev.get("vsBenchmark")}}
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    for r in archive:
        sc = r.get("scored_from_reports")
        print(f"{r['season']:>9} {r['start']} {r['days']}d n={r['models']} #1 {str(r['winner'])[:22]:22} {r['winner_return_pct']}% "
              f"trades #1={r['winner_trades']} per-model={r['trades_per_model']} needS={r['sharpe_needed_for_bar']} reports={r['daily_reports']}"
              + (f" | t>=2 {sc['t_ge_2']}/{sc['scored']} t>=bar {sc['t_ge_bar']} max {sc['max_t']}" if sc else ""))
    print(f"running {live['season']} day {live['days_elapsed']}: bar {live['bar_best_of_n']} t>=2 {live['t_ge_2']}/{live['scored']} max {live['max_t']}")
    for m in live["models"]:
        print(f"   {m['model']:16} {m['return_pct']:>6}% t={m['t']}")


if __name__ == "__main__":
    main()
