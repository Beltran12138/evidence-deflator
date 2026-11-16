import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import olas_predict_test as t  # noqa: E402
from forecast_score import bar  # noqa: E402

E18 = 10 ** 18


def omen_bet(agent, market, outcome, amount, tokens, answer):
    return {"bettor": {"id": agent}, "fixedProductMarketMaker": {"id": market, "currentAnswer": answer},
            "outcomeIndex": str(outcome), "amount": str(int(amount * E18)),
            "outcomeTokenAmount": str(int(tokens * E18))}


def ans(i):
    return "0x" + format(i, "064x")


def test_omen_buy_win_and_loss():
    bets = [omen_bet("a", "m1", 0, 6, 10, ans(0)),   # paid 6 for 10 tokens, won -> R = (10-6)/6
            omen_bet("a", "m2", 1, 6, 10, ans(0))]   # lost -> R = -1
    rows = {r["market"]: r for r in t.returns(t.positions(bets, "omen"), "omen")}
    assert abs(rows["m1"]["R"] - 4 / 6) < 1e-9 and rows["m1"]["won"]
    assert abs(rows["m2"]["R"] + 1) < 1e-9 and not rows["m2"]["won"]
    assert abs(rows["m1"]["price"] - 0.6) < 1e-9


def test_omen_sell_and_invalid_and_unresolved():
    bets = [omen_bet("a", "m1", 0, 6, 10, t.OMEN_INVALID),
            omen_bet("a", "m1", 0, -3, -4, t.OMEN_INVALID),  # sold 4 tokens for 3
            omen_bet("a", "m3", 0, 5, 10, None)]             # unresolved: left out
    rows = t.returns(t.positions(bets, "omen"), "omen")
    assert len(rows) == 1
    # holds 6 tokens, invalid pays 1/2 each = 3; cost = 6 - 3 = 3; R = (3 - 3) / 6 = 0
    assert abs(rows[0]["R"]) < 1e-9


def test_poly_payout_vector_and_negrisk():
    assert t.poly_payout_vector({"winningIndex": "1", "payouts": None}, 2) == [0.0, 1.0]
    assert t.poly_payout_vector({"winningIndex": "-1", "payouts": ["500000", "500000"]}, 2) == [0.5, 0.5]
    assert t.poly_payout_vector(None, 2) is None
    bets = [{"bettor": {"id": "a"}, "question": {"id": "q", "isNegRisk": True, "resolution": {"winningIndex": "0"}},
             "outcomeIndex": "0", "amount": "1000000", "shares": "2000000", "isBuy": True}]
    assert t.returns(t.positions(bets, "poly"), "poly") == []


def test_poly_buy_sell():
    res = {"winningIndex": "0", "payouts": None}
    bets = [{"bettor": {"id": "a"}, "question": {"id": "q", "isNegRisk": False, "resolution": res},
             "outcomeIndex": "0", "amount": "4000000", "shares": "10000000", "isBuy": True},
            {"bettor": {"id": "a"}, "question": {"id": "q", "isNegRisk": False, "resolution": res},
             "outcomeIndex": "0", "amount": "-2000000", "shares": "5000000", "isBuy": False}]
    r = t.returns(t.positions(bets, "poly"), "poly")[0]
    # holds 5, paid 4, got 2 back: payout 5, cost 2, R = 3/4
    assert abs(r["R"] - 0.75) < 1e-9


def test_spearman_and_ties():
    assert abs(t.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-12
    assert abs(t.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-12
    assert t.ranks([5, 5, 1]) == [2.5, 2.5, 1.0]


def test_no_skill_fleet_mostly_fails_bar():
    rng = random.Random(1)
    rows = []
    for a in range(200):
        for m in range(40):
            q = rng.uniform(0.1, 0.9)
            win = rng.random() < q   # fair price: no edge
            rows.append({"venue": "omen", "agent": "a%d" % a, "market": "m%d_%d" % (a, m),
                         "R": (1 / q - 1) if win else -1.0, "won": win, "price": q})
    res = t.analyse({"omen": rows})
    assert res["N_bar"] == 200 and abs(res["bar"] - bar(200)) < 1e-12
    assert len(res["pass_bar"]) <= 1
    v = res["venues"]["omen"]
    assert v["fleet_ci95"][0] < 0.05 and v["fleet_ci95"][1] > -0.2
    # win rate follows price when there is no skill
    assert v["rho_winrate_price"] > 0.3


def test_skilled_agent_is_found():
    rng = random.Random(2)
    rows = []
    for a in range(50):
        edge = 0.25 if a == 0 else 0.0
        for m in range(200):
            q = 0.5
            win = rng.random() < q + edge
            rows.append({"venue": "omen", "agent": "a%d" % a, "market": "m%d_%d" % (a, m),
                         "R": 1.0 if win else -1.0, "won": win, "price": q})
    res = t.analyse({"omen": rows})
    assert any(x["agent"] == "a0" for x in res["pass_bar"])
