"""Run the pre-registered Olas prediction-agent test (docs/data/olas/PREDICT_AGENTS_PREREG.md).

Unit: one agent in one resolved market. cost = buys paid - sells received; payout = tokens held
times what each outcome paid; R = (payout - cost) / buys paid. Per agent: t of mean R over its
markets, against the best-of-N bar with N = every agent with a resolved market. Standard library.

    python tools/olas_predict_test.py DATA_DIR OUT_JSON
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from forecast_score import bar  # noqa: E402

OMEN_INVALID = "0x" + "f" * 64
MIN_MARKETS = 20
MIN_AGENTS_RHO = 30
SEED = 20261116
DRAWS = 2000


# ---------- per-venue parsing into positions ----------

def omen_payout_vector(answer: Optional[str], k: int) -> Optional[List[float]]:
    """What one token of each outcome pays; None while unresolved."""
    if answer is None:
        return None
    if answer.lower() == OMEN_INVALID:
        return [1.0 / k] * k
    w = int(answer, 16)
    if w >= k:
        k = w + 1
    return [1.0 if i == w else 0.0 for i in range(k)]


def poly_payout_vector(res: Optional[dict], k: int) -> Optional[List[float]]:
    if not res:
        return None
    w = res.get("winningIndex")
    if w is not None and int(w) >= 0:
        w = int(w)
        k = max(k, w + 1)
        return [1.0 if i == w else 0.0 for i in range(k)]
    pay = [float(x) for x in (res.get("payouts") or [])]
    s = sum(pay)
    if s <= 0:
        return None
    return [x / s for x in pay]


def positions(bets: Iterable[dict], venue: str) -> Dict[Tuple[str, str], dict]:
    """(agent, market) -> {paid, received, tokens{outcome: n}, prices[], resolution, k}."""
    pos: Dict[Tuple[str, str], dict] = {}
    for b in bets:
        agent = b["bettor"]["id"]
        if venue == "omen":
            m = b["fixedProductMarketMaker"]
            if not m:
                continue
            mid, res = m["id"], m.get("currentAnswer")
            amt = int(b["amount"]) / 1e18
            tok = int(b["outcomeTokenAmount"]) / 1e18
            buy = amt > 0
        else:
            q = b["question"]
            if not q or q.get("isNegRisk"):
                continue
            mid, res = q["id"], q.get("resolution")
            amt = int(b["amount"]) / 1e6
            sh = abs(int(b["shares"])) / 1e6
            buy = bool(b["isBuy"])
            tok = sh if buy else -sh
        o = int(b["outcomeIndex"])
        p = pos.setdefault((agent, mid), {"paid": 0.0, "received": 0.0, "tokens": defaultdict(float),
                                          "bought": 0.0, "res": res, "k": 2})
        p["k"] = max(p["k"], o + 1)
        if buy:
            p["paid"] += amt
            p["bought"] += tok
        else:
            p["received"] += abs(amt)
        p["tokens"][o] += tok
    return pos


def returns(pos: Dict[Tuple[str, str], dict], venue: str) -> List[dict]:
    """One row per resolved agent-market with a buy."""
    out = []
    for (agent, mid), p in pos.items():
        if p["paid"] <= 0:
            continue
        vec = (omen_payout_vector if venue == "omen" else poly_payout_vector)(p["res"], p["k"])
        if vec is None:
            continue
        payout = sum(max(n, 0.0) * (vec[o] if o < len(vec) else 0.0) for o, n in p["tokens"].items())
        cost = p["paid"] - p["received"]
        out.append({"venue": venue, "agent": agent, "market": mid,
                    "R": (payout - cost) / p["paid"],
                    "won": payout > cost,
                    "price": p["paid"] / p["bought"] if p["bought"] > 0 else None})
    return out


# ---------- statistics ----------

def t_stat(xs: List[float]) -> Optional[float]:
    if len(xs) < 2:
        return None
    sd = statistics.stdev(xs)
    if sd == 0:
        return None
    return statistics.fmean(xs) / (sd / math.sqrt(len(xs)))


def ranks(xs: List[float]) -> List[float]:
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


def spearman(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    try:
        return statistics.correlation(ra, rb)
    except statistics.StatisticsError:
        return None


def bootstrap_mean_by_agent(rows: List[dict], draws: int = DRAWS, seed: int = SEED) -> Tuple[float, float, float]:
    by = defaultdict(list)
    for r in rows:
        by[r["agent"]].append(r["R"])
    groups = list(by.values())
    point = statistics.fmean([x for g in groups for x in g])
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        s, n = 0.0, 0
        for _ in range(len(groups)):
            g = groups[rng.randrange(len(groups))]
            s += sum(g)
            n += len(g)
        means.append(s / n)
    means.sort()
    return point, means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def effective_n_corr(rows: List[dict], agents: List[str], sample: int = 300, min_shared: int = 10,
                     seed: int = SEED) -> Optional[float]:
    """Median pairwise correlation of R among a seeded sample of agents sharing >= min_shared markets."""
    by: Dict[str, Dict[str, float]] = defaultdict(dict)
    for r in rows:
        by[r["agent"]][r["market"]] = r["R"]
    rng = random.Random(seed)
    pick = sorted(agents)
    if len(pick) > sample:
        pick = rng.sample(pick, sample)
    cs = []
    for i in range(len(pick)):
        for j in range(i + 1, len(pick)):
            a, b = by[pick[i]], by[pick[j]]
            shared = a.keys() & b.keys()
            if len(shared) >= min_shared:
                try:
                    cs.append(statistics.correlation([a[m] for m in shared], [b[m] for m in shared]))
                except statistics.StatisticsError:
                    pass
    return statistics.median(cs) if cs else None


def analyse(rows_by_venue: Dict[str, List[dict]]) -> dict:
    all_rows = [r for rows in rows_by_venue.values() for r in rows]
    agents_any = {(r["venue"], r["agent"]) for r in all_rows}
    n_bar = len(agents_any)
    b = bar(n_bar)
    per_agent = defaultdict(list)
    for r in all_rows:
        per_agent[(r["venue"], r["agent"])].append(r)
    table = []
    for key, rs in per_agent.items():
        if len(rs) < MIN_MARKETS:
            continue
        xs = [r["R"] for r in rs]
        prices = [r["price"] for r in rs if r["price"] is not None]
        table.append({"venue": key[0], "agent": key[1], "M": len(rs), "meanR": statistics.fmean(xs),
                      "t": t_stat(xs), "winrate": sum(r["won"] for r in rs) / len(rs),
                      "meanPrice": statistics.fmean(prices) if prices else None})
    with_t = [a for a in table if a["t"] is not None]
    out = {"N_bar": n_bar, "bar": b, "eligible": len(table), "eligible_with_t": len(with_t),
           "pass_bar": sorted([a for a in with_t if a["t"] >= b], key=lambda a: -a["t"]),
           "pass_2": sum(a["t"] >= 2 for a in with_t),
           "expected_pass_2": 0.02275 * len(with_t),
           "top5": sorted(with_t, key=lambda a: -a["t"])[:5],
           "venues": {}}
    for v, rows in rows_by_venue.items():
        el = [a for a in table if a["venue"] == v]
        vo = {"agents_with_resolved": len({r["agent"] for r in rows}), "agent_markets": len(rows),
              "eligible": len(el)}
        if rows:
            pt, lo, hi = bootstrap_mean_by_agent(rows)
            vo["fleet_meanR"] = pt
            vo["fleet_ci95"] = [lo, hi]
            vo["fleet_read"] = ("paid more than got back" if hi < 0 else
                                "beat market prices" if lo > 0 else "no conclusion")
        el_p = [a for a in el if a["meanPrice"] is not None]
        if len(el_p) >= MIN_AGENTS_RHO:
            vo["rho_winrate_price"] = spearman([a["winrate"] for a in el_p], [a["meanPrice"] for a in el_p])
            vo["rho_winrate_R"] = spearman([a["winrate"] for a in el_p], [a["meanR"] for a in el_p])
        vo["effective_n_median_corr"] = effective_n_corr(rows, [a["agent"] for a in el])
        out["venues"][v] = vo
    out["table"] = sorted(table, key=lambda a: (a["venue"], -(a["t"] or -1e9)))
    return out


def load(path: str) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main(argv):
    data_dir, out_path = argv[1], argv[2]
    rows = {}
    for v in ("omen", "poly"):
        p = os.path.join(data_dir, "%s_bets.jsonl" % v)
        if os.path.exists(p):
            rows[v] = returns(positions(load(p), v), v)
    res = analyse(rows)
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)
    show = {k: v for k, v in res.items() if k not in ("table",)}
    print(json.dumps(show, indent=1)[:6000])


if __name__ == "__main__":
    main(sys.argv)
