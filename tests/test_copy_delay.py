"""tools/copy_delay.py: price interpolation and the sign of the delay cost."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import copy_delay as C  # noqa: E402

M = 60000
# Two 15-minute candles: 100 -> 110, then 110 -> 90.
CS = [(0, 100.0, 110.0), (15 * M, 110.0, 90.0)]


def test_price_is_interpolated_inside_the_candle_and_none_outside():
    assert C.price_at(CS, 0) == 100.0
    assert C.price_at(CS, 7.5 * M) == pytest.approx(105.0)
    assert C.price_at(CS, 20 * M) == pytest.approx(110.0 - 20.0 * 5 / 15)
    assert C.price_at(CS, 30 * M) is None
    assert C.price_at(CS, -1) is None


def test_buying_late_into_a_rise_costs_and_selling_late_into_a_rise_pays():
    buy = {"coin": "X", "side": "B", "sz": "2", "px": "100", "time": 0}
    sell = {"coin": "X", "side": "A", "sz": "2", "px": "100", "time": 0}
    assert C.delay_cost([buy], {"X": CS}, 15)[0] == pytest.approx(2 * (110 - 100))
    assert C.delay_cost([sell], {"X": CS}, 15)[0] == pytest.approx(-2 * (110 - 100))


def test_fills_without_candles_are_skipped_and_counted():
    f = {"coin": "@107", "side": "B", "sz": "1", "px": "1", "time": 0}
    assert C.delay_cost([f], {"@107": []}, 15) == (0.0, 0, 1)
