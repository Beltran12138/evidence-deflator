"""tools/vault_follower_gap.py: the curve compounds PnL over capital, deposits included."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import vault_follower_gap as V  # noqa: E402


def test_curve_ignores_deposits_and_compounds_pnl():
    # 100 -> +10 PnL -> 110; then a 890 deposit and +100 PnL in one interval -> 1100.
    hist = [(0, 100.0), (1, 110.0), (2, 1100.0)]
    pnl = {0: 0.0, 1: 10.0, 2: 110.0}
    assert V.curve_return(hist, pnl, 0) == pytest.approx(1.1 * (1 + 100 / 1000) - 1)


def test_deposit_and_loss_in_one_interval_cannot_lose_more_than_capital():
    # 10 in the account, 1,000 deposited and 500 lost inside the same interval.
    hist = [(0, 10.0), (1, 510.0)]
    pnl = {0: 0.0, 1: -500.0}
    assert V.curve_return(hist, pnl, 0) == pytest.approx(-500 / 1010)
    assert V.rough_share(hist, pnl, 0) == 1.0


def test_entry_inside_an_interval_counts_the_part_after_it():
    hist = [(0, 100.0), (10, 120.0)]
    pnl = {0: 0.0, 10: 20.0}
    assert V.curve_return(hist, pnl, 5) == pytest.approx(0.5 * 20 / 100)
