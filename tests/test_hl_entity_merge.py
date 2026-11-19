import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from hl_entity_merge import merge  # noqa: E402
from liquidwhales_test import ranks, spearman  # noqa: E402


def pf(av, pnl):
    return {"allTime": {"accountValueHistory": [[t, str(v)] for t, v in av],
                        "pnlHistory": [[t, str(v)] for t, v in pnl]}}


def test_merge_sums_and_carries_forward():
    a = pf([(1, 100), (3, 110)], [(1, 0), (3, 10)])
    b = pf([(2, 50), (3, 40)], [(2, 0), (3, -10)])
    m = merge([a, b])["allTime"]
    av = [(t, float(v)) for t, v in m["accountValueHistory"]]
    pnl = [(t, float(v)) for t, v in m["pnlHistory"]]
    assert av == [(1, 100.0), (2, 150.0), (3, 150.0)]
    assert pnl == [(1, 0.0), (2, 0.0), (3, 0.0)]


def test_merge_single_account_is_identity():
    a = pf([(1, 100), (2, 120)], [(1, 0), (2, 20)])
    m = merge([a])["allTime"]
    assert [float(v) for _, v in m["pnlHistory"]] == [0.0, 20.0]
    assert [float(v) for _, v in m["accountValueHistory"]] == [100.0, 120.0]


def test_spearman_ties_and_order():
    assert ranks([3, 1, 1]) == [3.0, 1.5, 1.5]
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-12
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-12
