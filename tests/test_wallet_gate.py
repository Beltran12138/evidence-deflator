"""hl_wallet.check: clears_bar and bar_rule agree with the verdict, for a caller that gates on them."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

WEEK = 7 * 86400000


def portfolio(drift, weeks=60, seed=3):
    rng, pnl, av, out_av, out_pnl = random.Random(seed), 0.0, 10000.0, [], []
    for i in range(weeks):
        t = 1700000000000 + i * WEEK
        out_av.append([t, str(av)])
        out_pnl.append([t, str(pnl)])
        step = av * (drift + rng.gauss(0, 0.02))
        pnl += step
        av += step
    return {"allTime": {"accountValueHistory": out_av, "pnlHistory": out_pnl}}


def test_clears_bar_matches_verdict_blind_and_from_a_board():
    for drift in (0.03, 0.02, 0.004, -0.01):  # clears the board bar, only the blind bar, neither, loses
        pf = portfolio(drift)
        blind = H.check("0x" + "0" * 40, pf=pf)
        board = H.check("0x" + "0" * 40, picked_from=47270, pf=pf)
        assert blind["clears_bar"] == (blind["verdict"] == "clears_single")
        assert board["clears_bar"] == (board["verdict"] == "clears_board")
        assert blind["bar_rule"] == "picked blind: t >= 2"
        assert board["bar_rule"] == f"best of 47270: t >= {board['bar']}"


def test_a_short_record_never_clears():
    r = H.check("0x" + "0" * 40, pf=portfolio(0.05, weeks=4))
    assert r["verdict"] == "too_short" and r["clears_bar"] is False
