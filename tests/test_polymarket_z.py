"""z_cluster on Polymarket positions: the no-skill floor on the denominator (audit 2026-10-18).

The page (docs/assets/polymarket.js) and the offline audit (tools/audit_polymarket.py) compute the same
statistic; both are checked against the same cases.
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import audit_polymarket as A  # noqa: E402


def pos(event, price, won, market=None, side="Yes"):
    market = market or f"{event}-m"
    return {"eventSlug": event, "conditionId": market, "asset": f"{market}-{side}",
            "avgPrice": price, "curPrice": 1 if won else 0, "totalBought": 100}


def favourites(n, price=0.995):
    return [pos(f"e{i}", price, True) for i in range(n)]


def hedged():
    # Both sides of one market (one always pays) plus one single-sided bet in another event.
    return [pos("e1", 0.58, True, "m1", "Yes"), pos("e1", 0.41, False, "m1", "No"), pos("e2", 0.35, True)]


def test_favourites_only_wallet_does_not_clear_the_bar():
    # Thirty wins bought at 0.995 scored 5.48 before the floor; under no skill they are near-certain wins.
    z = A.test(favourites(30))["z_cluster"]
    assert z < 1
    assert z == pytest.approx(30 * 0.005 / math.sqrt(30 * 0.995 * 0.005), abs=0.01)


def test_two_sided_market_adds_nothing_to_the_floor():
    # Floor counts only e2's bet (0.35 * 0.65); realised: e1 edge 0.01, e2 edge 0.65.
    r = A.test(hedged())
    assert r["z_cluster"] == pytest.approx(0.66 / math.sqrt(max(0.01 ** 2 + 0.65 ** 2, 0.35 * 0.65)), abs=0.01)


def test_no_skill_false_positive_rate_for_favourite_buyers_is_at_most_nominal():
    # Before the floor, 47% of no-skill favourite buyers with 9 events reached z >= 2.
    rng, hits, trials = random.Random(7), 0, 4000
    for _ in range(trials):
        ps = []
        for i in range(9):
            p = rng.uniform(0.85, 0.99)
            ps.append(pos(f"e{i}", p, rng.random() < p))
        hits += (A.test(ps)["z_cluster"] or 0) >= 2
    assert hits / trials <= 0.023


def test_no_skill_false_positive_rate_mid_prices_stays_near_nominal():
    rng, hits, trials = random.Random(11), 0, 4000
    for _ in range(trials):
        ps = []
        for i in range(30):
            p = rng.uniform(0.05, 0.95)
            ps.append(pos(f"e{i}", p, rng.random() < p))
        hits += (A.test(ps)["z_cluster"] or 0) >= 2
    assert 0.01 <= hits / trials <= 0.035


def _js_test_fn():
    src = open(os.path.join(ROOT, "docs", "assets", "polymarket.js"), encoding="utf-8").read()
    start = src.index("function test(pos)")
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[start:i + 1]
        i += 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("case", [favourites(30), hedged(), favourites(9, 0.9)])
def test_page_matches_audit(case, tmp_path):
    script = tmp_path / "run.js"
    script.write_text(_js_test_fn() + f"\nconsole.log(JSON.stringify(test({json.dumps(case)})));\n", encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    assert out["z"] == pytest.approx(A.test(case)["z_cluster"], abs=0.006)
