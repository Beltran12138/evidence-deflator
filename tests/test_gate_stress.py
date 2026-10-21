import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gate_stress as gs  # noqa: E402

RULES = {"allow": ["BTC", "ETH"], "max_order_usd": 500, "max_daily_loss_usd": 200, "max_orders_per_day": 20}
FLAT = [{"BTC": 0.0, "ETH": 0.0}] * 24
CRASH = [{"BTC": -0.01, "ETH": -0.01}] * 24     # about -21% over the day


def test_flat_market_max_out_builds_every_allowed_order():
    r = gs.simulate(RULES, [FLAT], "max_out", 3, 10_000, random.Random(1))
    assert abs(r["end_exposure"] - 3 * 20 * 500) < 1e-6 and r["worst_day_loss"] == 0


def test_position_limit_holds_exposure_down():
    r = gs.simulate(dict(RULES, max_position_usd=1000), [FLAT], "max_out", 3, 10_000, random.Random(1))
    assert abs(r["end_exposure"] - 2 * 1000) < 1e-6


def test_daily_loss_limit_does_not_cap_the_day():
    """Two flat days build $20,000 of longs; on the crash day the limit stops new buys, not the fall."""
    blocks_seq = iter([FLAT, FLAT, CRASH])

    class Seq(random.Random):
        def choice(self, seq):
            if seq and isinstance(seq[0], list):   # picking a day block
                return next(blocks_seq)
            return super().choice(seq)

    r = gs.simulate(RULES, [FLAT, CRASH], "max_out", 3, 10_000, Seq(2))
    assert r["worst_day_loss"] > 10 * RULES["max_daily_loss_usd"] and r["days_over_limit"] == 1


def test_aligned_day_blocks_keeps_only_whole_common_days():
    h = 3_600_000
    day0 = 86_400_000 * 20000
    btc = [[day0 + i * h, 100 + i] for i in range(0, 49)]           # two whole days of returns (+1 base candle)
    eth = [[day0 + i * h, 50 + i] for i in range(0, 49) if i != 30]  # a missing candle breaks day 2
    # returns exist at hours 1..48: day 0 has 23, day 1 has all 24, day 2 has 1 -> one whole day
    full = gs.aligned_day_blocks({"BTC": btc, "ETH": [[t, 50 + k] for k, (t, _) in enumerate(btc)]})
    assert len(full) == 1 and len(full[0]) == 24 and set(full[0][0]) == {"BTC", "ETH"}
    # ETH missing the candle at hour 30 (day 1) loses two returns there, so day 1 is no longer whole
    assert gs.aligned_day_blocks({"BTC": btc, "ETH": eth}) == []


def test_stress_is_reproducible():
    a = gs.stress(RULES, [FLAT, CRASH], days=5, sims=20)
    b = gs.stress(RULES, [FLAT, CRASH], days=5, sims=20)
    assert a == b and set(a) == {"max_out", "random"}
