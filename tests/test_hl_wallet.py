"""src/hl_wallet.py: verdict keys and the offline check() path used by the MCP tool."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hl_wallet as hw  # noqa: E402

W = hw.WEEK_MS


def portfolio(points):
    return {"allTime": {"accountValueHistory": [[t, str(v)] for t, v, _ in points],
                        "pnlHistory": [[t, str(p)] for t, _, p in points]}}


def test_verdict_keys_match_the_browser():
    assert hw.verdict({"t": None})["key"] == "too_short"
    assert hw.verdict({"t": 1.0})["key"] == "luck"
    assert hw.verdict({"t": -2.5})["key"] == "loses"
    assert hw.verdict({"t": 3.0})["key"] == "clears_single"
    assert hw.verdict({"t": 3.0}, picked_from=47_153)["key"] == "clears_single"
    assert hw.verdict({"t": 5.5}, picked_from=47_153) == {"key": "clears_board", "bar": 4.9}
    # without a board size there is no board bar to clear
    assert hw.verdict({"t": 5.5})["key"] == "clears_single"


def test_check_scores_a_given_portfolio_without_the_network():
    # weekly returns alternate +2.2% / -0.2%: mean 1%, sd 1.2%, 59 intervals, t about 6.4
    pts, pnl = [], 0.0
    for i in range(60):
        pts.append((i * W, 50_000.0, pnl))
        pnl += 50_000.0 * (0.022 if i % 2 == 0 else -0.002)
    r = hw.check("0x" + "0" * 40, picked_from=47_153, pf=portfolio(pts))
    assert r["intervals"] == 59 and r["dof"] == 58
    assert r["verdict"] == "clears_board" and r["bar"] == 4.9
    assert r["history_from"] == "1970-01-01" and r["flags"] == []


def test_luck_is_the_tail_for_one_and_any_of_n_for_many():
    assert abs(hw.luck(2.0) - 0.0227501) < 1e-6
    # best of n with no skill: 1 - (1 - tail)^n; at bar(n) that is about alpha again
    n = 47_248
    assert abs(hw.luck(hw.bar(n), n) - hw.ALPHA) < 1e-3
    assert hw.luck(None) is None and hw.luck(-1.0) > 0.8


def candles_from(prices, t0=0, step=W):
    return [{"t": t0 + i * step - step, "T": t0 + i * step, "c": str(p)} for i, p in enumerate(prices)]


def test_bench_returns_match_intervals_by_date():
    c = candles_from([100, 110, 99])
    iv = [(0.0, 1.0, 0, W), (0.0, 1.0, W, 2 * W), (0.0, 1.0, -W, 0)]
    out = hw.bench_returns(c, iv)
    assert abs(out[0] - 0.10) < 1e-12 and abs(out[1] + 0.10) < 1e-12 and out[2] is None


def test_alpha_vs_recovers_beta_and_drops_the_market():
    # returns = 0.4 x BTC + small noise and no drift: raw t is large in a rising market, alpha t is not
    btc = [0.03 if i % 3 else -0.01 for i in range(80)]
    noise = [0.002 * ((i * 7) % 5 - 2) for i in range(80)]
    iv = [(0.4 * b + e, 1.0, i * W, (i + 1) * W) for i, (b, e) in enumerate(zip(btc, noise))]
    raw = hw.score([(r, w) for r, w, _, _ in iv])
    adj = hw.alpha_vs(iv, btc)
    assert abs(adj["beta_btc"] - 0.4) < 0.01 and adj["n_btc"] == 80
    assert raw["t"] > 4 and abs(adj["t_btc"]) < 2
    # too few intervals with a benchmark: no number
    assert hw.alpha_vs(iv[:5], btc[:5])["t_btc"] is None


def test_check_offline_with_candles_reports_btc_adjusted_t():
    pts, pnl, prices = [], 0.0, [100.0]
    for i in range(30):
        pts.append((i * W, 50_000.0, pnl))
        pnl += 50_000.0 * (0.01 + (0.004 if i % 2 else -0.004))
        prices.append(prices[-1] * (1.02 if i % 3 else 0.97))
    r = hw.check("0x" + "0" * 40, pf=portfolio(pts), candles=candles_from(prices, t0=0))
    assert r["t_btc"] is not None and r["n_btc"] == 29
    assert hw.check("0x" + "0" * 40, pf=portfolio(pts))["t_btc"] is None
