"""tools/vault_flow_test.py: flow arithmetic, closed vaults, and that the partial correlation removes R."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import vault_flow_test as V  # noqa: E402

DAY = V.DAY
WEEK = 7 * DAY


def vault(av, pnl, closed=False, start=0):
    return {"av": [[start + i * WEEK, a] for i, a in enumerate(av)],
            "pnl": [[start + i * WEEK, p] for i, p in enumerate(pnl)], "closed": closed}


def test_interp_holds_last_sample_only_for_closed_vaults():
    s = [(0, 10.0), (10, 20.0)]
    assert V.interp(s, 5, False) == pytest.approx(15.0)
    assert V.interp(s, 20, False) is None
    assert V.interp(s, 20, True) == 20.0
    assert V.interp(s, -1, True) is None


def test_flow_is_account_change_minus_pnl_over_account_value():
    # 20 weekly samples, steady 1% gains on 100k; a 50k deposit lands in week 15.
    av, pnl, a, p = [], [], 100_000.0, 0.0
    for i in range(20):
        if i == 15:
            a += 50_000.0
        av.append(a)
        pnl.append(p)
        g = a * 0.01
        a += g
        p += g
    # gains alternate a little so the weekly series has spread
    v = vault(av, pnl)
    t = 12 * WEEK
    o = V.observe(v, t)
    assert isinstance(o, dict), o
    a0, p0 = V.interp([(x, y) for x, y in v["av"]], t, False), V.interp([(x, y) for x, y in v["pnl"]], t, False)
    a1, p1 = V.interp([(x, y) for x, y in v["av"]], t + 30 * DAY, False), V.interp([(x, y) for x, y in v["pnl"]], t + 30 * DAY, False)
    assert o["F"] == pytest.approx(((a1 - a0) - (p1 - p0)) / a0)
    assert o["F"] > 0.3  # the 50k deposit, not the PnL


def test_vault_below_50k_or_too_short_is_left_out():
    small = vault([10_000.0 * (1.01 ** i) for i in range(20)], [100.0 * i for i in range(20)])
    assert V.observe(small, 12 * WEEK) == "below_50k"
    short = vault([100_000.0 + 500 * (i % 2) for i in range(20)], [500.0 * (i % 2) for i in range(20)])
    assert V.observe(short, 3 * WEEK) == "under_8_weeks"  # 3 weeks of record, outcome inside history


def test_closed_vault_that_emptied_shows_the_outflow():
    av = [100_000.0 + 1000 * (i % 3) for i in range(14)] + [0.0]
    pnl = [1000.0 * (i % 3) + 50 * i for i in range(14)] + [1000.0 * (13 % 3) + 50 * 13]
    v = vault(av, pnl, closed=True)
    o = V.observe(v, 13 * WEEK)
    assert isinstance(o, dict), o
    assert o["F"] < -0.9


def test_partial_correlation_removes_what_r_explains():
    rng = np.random.default_rng(1)
    n = 400
    R = rng.normal(size=n)
    S = R + rng.normal(scale=0.5, size=n)  # S strongly tied to R
    L = rng.normal(size=n)
    F_chase = R + rng.normal(scale=0.3, size=n)  # flows follow R only
    m = V.month_stats(F_chase, R, S, L)
    assert m["rho_FR"] > 0.8
    assert abs(m["partial_FS_R"]) < 0.1  # S looks related to F only through R
    F_cred = R + 2 * (S - R) + rng.normal(scale=0.3, size=n)  # flows also follow S beyond R
    assert V.month_stats(F_cred, R, S, L)["partial_FS_R"] > 0.5


def test_ranks_average_ties():
    assert list(V.ranks([3, 1, 3, 2])) == [2.5, 0.0, 2.5, 1.0]


def test_rough_rule_applies_only_in_the_sensitivity_run():
    # Big deposits and withdrawals every other week: rough, but the primary run keeps it (Amendment 1).
    av, pnl, a, p = [], [], 100_000.0, 0.0
    for i in range(20):
        a += 60_000.0 if i % 2 else -40_000.0
        g = a * (0.01 if i % 3 else -0.005)
        av.append(a)
        pnl.append(p)
        a += g
        p += g
    v = vault(av, pnl)
    assert isinstance(V.observe(v, 12 * WEEK), dict)
    assert V.observe(v, 12 * WEEK, rough_max=0.10) == "rough"
