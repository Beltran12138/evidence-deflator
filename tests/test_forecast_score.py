import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import forecast_score as fs  # noqa: E402


def _calls(n, seed, sharp, ref_noise=None):
    """Truth q ~ U(0,1); forecaster says q pulled toward 0.5 by (1 - sharp); outcome ~ Bern(q)."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        q = rnd.random()
        p = 0.5 + sharp * (q - 0.5)
        ref = None if ref_noise is None else min(max(q + rnd.gauss(0, ref_noise), 0.01), 0.99)
        out.append({"p": p, "o": 1 if rnd.random() < q else 0, "ref": ref, "pnl": None})
    return out


def test_no_information_is_luck_most_of_the_time():
    # a forecaster who always says 0.5 against a coin flip: gain is exactly 0
    calls = [{"p": 0.5, "o": i % 2, "ref": None, "pnl": None} for i in range(100)]
    s = fs.score(calls)
    assert s["verdict"] == "no_spread"


def test_null_false_positive_rate_near_nominal():
    # forecaster and reference are equally good (same information, independent noise): ~2.3% clear 2
    hits = 0
    for k in range(400):
        rnd = random.Random(k)
        calls = []
        for _ in range(200):
            q = rnd.random()
            o = 1 if rnd.random() < q else 0
            calls.append({"p": min(max(q + rnd.gauss(0, 0.1), 0.01), 0.99), "o": o,
                          "ref": min(max(q + rnd.gauss(0, 0.1), 0.01), 0.99), "pnl": None})
        hits += fs.score(calls)["verdict"] == "clears"
    assert hits / 400 < 0.06


def test_informed_forecaster_clears_coin_flip():
    s = fs.score(_calls(400, 1, sharp=1.0))
    assert s["verdict"] == "clears"
    assert s["calibration"]["reliability"] < 0.01


def test_overconfident_shows_in_reliability():
    good = fs.score(_calls(2000, 2, sharp=1.0))["calibration"]["reliability"]
    over = [dict(c, p=min(max(0.5 + 1.8 * (c["p"] - 0.5), 0.01), 0.99)) for c in _calls(2000, 2, sharp=1.0)]
    assert fs.score(over)["calibration"]["reliability"] > 3 * good


def test_best_of_n_raises_bar():
    calls = _calls(150, 5, sharp=0.6)
    one, many = fs.score(calls), fs.score(calls, picked_from=50)
    assert many["bar"] > one["bar"] == 2.0


def test_parse_percent_and_csv_columns():
    rows = fs.parse([{"p": "70", "outcome": "1", "ref": "55", "pnl": "12.5"},
                     {"p": "0.2", "outcome": "0", "ref": "", "pnl": ""}])
    assert rows[0]["p"] == 0.7 and rows[0]["ref"] == 0.55 and rows[0]["pnl"] == 12.5
    assert rows[1]["ref"] is None and rows[1]["pnl"] is None
