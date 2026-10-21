"""Put the agent gate in front of other open-source trading agents' order paths.

Each adapter turns the host project's broker into the three calls the gate needs (account, price,
submit) and routes the host's orders through ``agent_gate.Gate.place``, so the host gets the same
rules or signed mandate, the same ledger and the same audit as the gate's own brokers. None of
these import the host project; they work on its objects by shape.

  ai-hedge-fund (virattt)   GatedHedgeFundBroker wraps any object with its Broker protocol
                            (positions / cash / place_order). A refused order raises, which is that
                            protocol's contract for an order that cannot be filled completely.
  lumibot (Lumiwealth)      GatedStrategyMixin, listed before Strategy in the class bases, checks
                            every submit_order; a refused order is logged and not sent.
  TradingAgents (Tauric)    It ends with a rating and places nothing. execute_rating turns a rating
                            into one gated order with sizes the owner sets; nothing trades on its own.

The adapters do not change what the host decides; the gate only refuses what breaks the owner's limits.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_gate  # noqa: E402


class GateRefused(RuntimeError):
    """The gate refused the order; ``entry`` is the ledger line that records why."""

    def __init__(self, entry: Dict[str, Any]):
        self.entry = entry
        super().__init__("agent gate refused the order: " + "; ".join(entry.get("reasons") or []))


class CallbackBroker:
    """The gate's broker interface over three callables supplied by an adapter."""

    name = "external"

    def __init__(self, account: Callable[[], Dict[str, Any]], price: Callable[[str], float],
                 submit: Callable[[str, str, float, float], Dict[str, Any]]):
        self.account, self.price, self.submit = account, price, submit


def _gate(cfg: Any, broker: CallbackBroker) -> agent_gate.Gate:
    if isinstance(cfg, str):
        cfg = agent_gate.load_config(cfg)
    return agent_gate.Gate(cfg, broker=broker)


# ---------------------------------------------------------------- ai-hedge-fund

class GatedHedgeFundBroker:
    """ai-hedge-fund's Broker protocol (hedge_fund/brokers/protocol.py), gated.

    ``inner`` is the fund's real broker (SimBroker, PaperBroker or a live one). Orders carry their own
    reference price, which is what the gate checks the size against. That protocol has no equity
    call, so equity for the daily-loss rule is cash plus positions at the last price the gate saw
    for each ticker; a ticker never ordered through the gate counts at zero until it is.

    The fund places a cycle's orders one by one, so a refusal in the middle leaves the earlier ones
    filled; the fund's reconciliation then stops the next session until someone looks, which is the
    fail-closed outcome the protocol intends.
    """

    def __init__(self, inner: Any, config: Any):
        self.inner = inner
        self._marks: Dict[str, float] = {}
        self._pending: Optional[Any] = None
        self._last_fill: Any = None
        self.gate = _gate(config, CallbackBroker(self._account, self._price, self._submit))

    # the protocol
    def positions(self):
        return self.inner.positions()

    def cash(self) -> float:
        return self.inner.cash()

    def place_order(self, order: Any):
        self._pending = order
        self._marks[order.ticker.upper()] = float(order.price)
        try:
            e = self.gate.place(order.ticker, order.side, qty=float(order.quantity), note="ai-hedge-fund")
        finally:
            self._pending = None
        if e["decision"] != "allow":
            raise GateRefused(e)
        return self._last_fill

    # what the gate calls
    def _account(self) -> Dict[str, Any]:
        cash = float(self.inner.cash())
        pos = {t.upper(): float(p.shares) for t, p in self.inner.positions().items()}
        return {"cash": cash, "positions": pos,
                "equity": round(cash + sum(q * self._marks.get(t, 0.0) for t, q in pos.items()), 2)}

    def _price(self, symbol: str) -> float:
        if self._pending is not None and self._pending.ticker.upper() == symbol.upper():
            return float(self._pending.price)
        if symbol.upper() in self._marks:
            return self._marks[symbol.upper()]
        raise ValueError(f"no reference price for {symbol}")

    def _submit(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        o = self._pending
        fill = self.inner.place_order(o)
        self._last_fill = fill
        return {"status": "filled", "symbol": fill.ticker, "side": fill.side,
                "qty": float(fill.quantity), "price": float(fill.price)}


# ---------------------------------------------------------------- lumibot

class GatedStrategyMixin:
    """Mix into a lumibot Strategy (``class Bot(GatedStrategyMixin, Strategy)``) and set ``gate_config``.

    Every order passed to submit_order is checked first; refused orders are logged with the gate's
    reasons and not sent; allowed ones go on to lumibot's own submit_order unchanged. Price is the
    order's limit price if it has one, else get_last_price; equity is get_portfolio_value.
    """

    gate_config: Any = None
    _gate_obj: Optional[agent_gate.Gate] = None
    _gate_pending: Any = None
    _gate_result: Any = None

    def _gate(self) -> agent_gate.Gate:
        if self._gate_obj is None:
            self._gate_obj = _gate(self.gate_config, CallbackBroker(self._g_account, self._g_price, self._g_submit))
        return self._gate_obj

    def submit_order(self, order, *args, **kwargs):  # noqa: D401 - lumibot's signature
        if isinstance(order, (list, tuple)):
            return [r for r in (self.submit_order(o, *args, **kwargs) for o in order) if r is not None]
        self._gate_pending = (order, args, kwargs)
        self._gate_result = None
        s = str(getattr(order.side, "value", order.side)).lower().split(".")[-1]  # buy, sell_to_close, sell_short…
        side = "buy" if s.startswith("buy") else "sell" if s.startswith("sell") else s
        try:
            e = self._gate().place(order.asset.symbol, side, qty=float(order.quantity),
                                   note=str(kwargs.get("reason") or "lumibot"))
        finally:
            self._gate_pending = None
        if e["decision"] != "allow":
            log = getattr(self, "log_message", print)
            log("agent gate refused %s %s: %s" % (order.side, order.asset.symbol, "; ".join(e["reasons"])))
            return None
        return self._gate_result

    def _g_account(self) -> Dict[str, Any]:
        pos = {}
        for p in self.get_positions() or []:
            sym = getattr(getattr(p, "asset", None), "symbol", None)
            if sym and sym.upper() != "USD":
                pos[sym.upper()] = float(p.quantity)
        return {"cash": float(self.get_cash() or 0.0), "positions": pos,
                "equity": float(self.get_portfolio_value() or 0.0)}

    def _g_price(self, symbol: str) -> float:
        order = self._gate_pending[0] if self._gate_pending else None
        if order is not None and getattr(order, "limit_price", None):
            return float(order.limit_price)
        p = self.get_last_price(symbol)
        if p is None:
            raise ValueError(f"no price for {symbol}")
        return float(p)

    def _g_submit(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        order, args, kwargs = self._gate_pending
        self._gate_result = super().submit_order(order, *args, **kwargs)
        oid = getattr(self._gate_result, "identifier", None)
        return {"status": "submitted", "symbol": symbol, "side": side, "qty": qty, "id": oid}


# ---------------------------------------------------------------- TradingAgents

def execute_rating(gate: agent_gate.Gate, symbol: str, rating: str, buy_usd: Dict[str, float],
                   sell_fraction: Dict[str, float], note: str = "") -> Optional[Dict[str, Any]]:
    """Turn one TradingAgents rating into at most one gated order.

    ``buy_usd`` maps the bullish ratings you want to act on to a dollar size, e.g. {"Buy": 200};
    ``sell_fraction`` maps the bearish ones to the share of the current position to sell, e.g.
    {"Sell": 1.0, "Underweight": 0.5}. A rating missing from both, "Hold" and "REVIEW" (no readable
    rating) place nothing. The sizes are yours; the default is to do nothing. Sells only reduce a
    long position, so a bearish rating never opens a short through this function.
    """
    r = (rating or "").strip().capitalize() if rating != "REVIEW" else "REVIEW"
    if r in buy_usd and buy_usd[r] > 0:
        return gate.place(symbol, "buy", usd=float(buy_usd[r]), note=note or f"TradingAgents: {r}")
    if r in sell_fraction and sell_fraction[r] > 0:
        held = float(gate.broker.account()["positions"].get(symbol.upper(), 0.0))
        if held <= 0:
            return None
        return gate.place(symbol, "sell", qty=held * min(1.0, float(sell_fraction[r])),
                          note=note or f"TradingAgents: {r}")
    return None
