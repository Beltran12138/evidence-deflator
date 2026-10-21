import os
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_gate as ag  # noqa: E402
import gate_adapters as ga  # noqa: E402

RULES = {"allow": ["AAPL", "MSFT"], "max_order_usd": 1000, "max_daily_loss_usd": 200, "max_orders_per_day": 20}


def cfg(tmp_path, **kw):
    return dict(ag.DEFAULTS, state_dir=str(tmp_path), **dict(RULES, **kw))


# ---------------------------------------------------------------- ai-hedge-fund shapes

class FundSim:
    """The shape of ai-hedge-fund's SimBroker: fills completely at the order's price or raises."""

    def __init__(self, cash):
        self._cash, self._shares = cash, {}

    def positions(self):
        return {t: NS(ticker=t, shares=s) for t, s in self._shares.items() if s}

    def cash(self):
        return self._cash

    def place_order(self, o):
        sign = 1 if o.side == "buy" else -1
        self._shares[o.ticker] = self._shares.get(o.ticker, 0) + sign * o.quantity
        self._cash -= sign * o.quantity * o.price
        return NS(ticker=o.ticker, side=o.side, quantity=o.quantity, price=o.price)


def order(t, side, q, px):
    return NS(ticker=t, side=side, quantity=q, price=px)


def test_hedge_fund_allowed_order_fills_and_is_logged(tmp_path):
    inner = FundSim(10_000)
    b = ga.GatedHedgeFundBroker(inner, cfg(tmp_path))
    fill = b.place_order(order("AAPL", "buy", 4, 200.0))
    assert fill.quantity == 4 and inner.positions()["AAPL"].shares == 4
    rows = b.gate.ledger.read()
    assert rows[-1]["decision"] == "allow" and rows[-1]["fill"]["qty"] == 4.0
    assert b.positions() == inner.positions() and b.cash() == inner.cash()


def test_hedge_fund_refusal_raises_and_never_reaches_the_broker(tmp_path):
    inner = FundSim(10_000)
    b = ga.GatedHedgeFundBroker(inner, cfg(tmp_path))
    with pytest.raises(ga.GateRefused) as ex:
        b.place_order(order("AAPL", "buy", 10, 200.0))  # $2,000 > $1,000
    assert "single-order limit" in str(ex.value)
    with pytest.raises(ga.GateRefused):
        b.place_order(order("TSLA", "buy", 1, 200.0))  # off the allow list
    assert inner.positions() == {} and inner.cash() == 10_000
    assert [r["decision"] for r in b.gate.ledger.read()] == ["block", "block"]


def test_hedge_fund_daily_loss_uses_marks_and_still_lets_it_sell(tmp_path):
    inner = FundSim(10_000)
    t = [1_790_000_000.0]
    b = ga.GatedHedgeFundBroker(inner, cfg(tmp_path))
    b.gate.clock = lambda: t[0]
    b.place_order(order("AAPL", "buy", 5, 200.0))          # equity 10,000
    t[0] += 60
    with pytest.raises(ga.GateRefused) as ex:               # AAPL marked at 150: down $250 today
        b.place_order(order("AAPL", "buy", 1, 150.0))
    assert "daily-loss" in str(ex.value)
    t[0] += 60
    assert b.place_order(order("AAPL", "sell", 5, 150.0)).quantity == 5   # reducing still passes


# ---------------------------------------------------------------- lumibot shapes

class FakeStrategy:
    """The parts of lumibot's Strategy the mixin touches."""

    def __init__(self):
        self.sent, self.logs, self.cash = [], [], 10_000.0
        self.pos = {}

    def submit_order(self, order, *args, **kwargs):
        self.sent.append(order)
        q = order.quantity if str(order.side).startswith("buy") else -order.quantity
        self.pos[order.asset.symbol] = self.pos.get(order.asset.symbol, 0) + q
        return NS(identifier="oid-%d" % len(self.sent))

    def get_positions(self):
        return [NS(asset=NS(symbol=s), quantity=q) for s, q in self.pos.items()] + [NS(asset=NS(symbol="USD"), quantity=1)]

    def get_cash(self):
        return self.cash

    def get_portfolio_value(self):
        return 10_000.0

    def get_last_price(self, symbol):
        return {"AAPL": 200.0, "MSFT": 400.0, "TSLA": 250.0}.get(symbol)

    def log_message(self, m):
        self.logs.append(m)


def lumi_order(sym, side, q, limit=None):
    return NS(asset=NS(symbol=sym), side=side, quantity=q, limit_price=limit)


def test_lumibot_mixin_sends_allowed_and_drops_refused(tmp_path):
    class Bot(ga.GatedStrategyMixin, FakeStrategy):
        gate_config = cfg(tmp_path)

    bot = Bot()
    r = bot.submit_order(lumi_order("AAPL", "buy", 2), reason="momentum")
    assert r.identifier == "oid-1" and len(bot.sent) == 1
    assert bot.submit_order(lumi_order("MSFT", "buy", 5)) is None            # $2,000 > $1,000
    assert bot.submit_order(lumi_order("TSLA", "buy", 1)) is None            # off the list
    assert len(bot.sent) == 1 and len(bot.logs) == 2 and "single-order limit" in bot.logs[0]
    rows = bot._gate().ledger.read()
    assert rows[0]["request"]["note"] == "momentum" and rows[0]["fill"]["id"] == "oid-1"


def test_lumibot_mixin_reads_limit_price_and_side_variants(tmp_path):
    class Bot(ga.GatedStrategyMixin, FakeStrategy):
        gate_config = cfg(tmp_path)

    bot = Bot()
    bot.pos["AAPL"] = 10
    # limit at 90 makes 10 shares $900, under the $1,000 limit; the last price would make it $2,000
    assert bot.submit_order(lumi_order("AAPL", "sell_to_close", 10, limit=90.0)) is not None
    out = bot.submit_order([lumi_order("AAPL", "buy", 1), lumi_order("MSFT", "buy", 9)])
    assert len(out) == 1


# ---------------------------------------------------------------- TradingAgents

def test_execute_rating_only_trades_what_the_owner_sized(tmp_path):
    g = ag.Gate(cfg(tmp_path, allow=["NVDA"]), ag.SimBroker(str(tmp_path), 10_000, lambda: {"NVDA": 100.0}))
    assert ga.execute_rating(g, "NVDA", "Hold", {"Buy": 200}, {"Sell": 1.0}) is None
    assert ga.execute_rating(g, "NVDA", "REVIEW", {"Buy": 200}, {"Sell": 1.0}) is None
    assert ga.execute_rating(g, "NVDA", "Overweight", {"Buy": 200}, {"Sell": 1.0}) is None   # not sized
    assert ga.execute_rating(g, "NVDA", "Sell", {"Buy": 200}, {"Sell": 1.0}) is None          # nothing held
    e = ga.execute_rating(g, "NVDA", "Buy", {"Buy": 200}, {"Sell": 1.0})
    assert e["decision"] == "allow" and abs(e["request"]["qty"] - 2.0) < 1e-9
    e = ga.execute_rating(g, "NVDA", "sell", {"Buy": 200}, {"Sell": 1.0})
    assert e["request"]["side"] == "sell" and abs(e["request"]["qty"] - 2.0) < 1e-9
    big = ga.execute_rating(g, "NVDA", "Buy", {"Buy": 5000}, {})
    assert big["decision"] == "block"
