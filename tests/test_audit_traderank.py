"""audit_traderank: cycle-close equity becomes (return, weeks) pairs, and a field is scored against bar(n)."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import audit_traderank as A  # noqa: E402

DAY = 86400000


def test_returns_and_intervals_from_cycle_closes():
    r = A.rets_from_values([(2 * DAY, 11000.0), (0, 10000.0), (3 * DAY, 11000.0)])  # unsorted on purpose
    assert [round(x, 6) for x, _ in r] == [0.1, 0.0]
    assert [round(w, 6) for _, w in r] == [round(2 / 7, 6), round(1 / 7, 6)]


def test_a_flat_account_is_not_scored_and_a_noisy_field_does_not_clear():
    rng = random.Random(5)
    series = {"flat": [(i * DAY, 10000.0) for i in range(10)]}
    for k in range(21):
        v, pts = 10000.0, []
        for i in range(10):
            pts.append((i * DAY, v))
            v *= 1 + rng.gauss(0, 0.01)
        series[f"m{k}"] = pts
    f = A.scored_field(series, 22)
    assert f["bar_best_of_n"] == 3.08
    assert f["scored"] == 21 and next(m for m in f["models"] if m["model"] == "flat")["t"] is None
    assert f["t_ge_bar"] == 0
