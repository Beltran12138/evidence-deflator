# Using the gate with other open-source trading agents

`src/gate_adapters.py` puts the gate (rules or a signed mandate, the ledger, `audit`) in front of the order path of three widely used projects. Nothing here needs a change in those projects; each adapter wraps the project's own objects.

| Project | What it does with orders | Adapter | Tested how |
|---|---|---|---|
| [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) (virattt) | Places orders through a `Broker` protocol: `positions`, `cash`, `place_order` | `GatedHedgeFundBroker(inner_broker, "gate.json")` | Unit tests with a fake of that protocol. Also run against the project's real `SimBroker` and pydantic `Order`/`Fill`: one allowed fill, two refusals, and the wrapper passes `isinstance(…, Broker)` on its `runtime_checkable` protocol (2026-10-21) |
| [lumibot](https://github.com/Lumiwealth/lumibot) (Lumiwealth) | Strategies call `submit_order`, which goes to one of a dozen brokers | `class Bot(GatedStrategyMixin, Strategy): gate_config = "gate.json"` | Unit tests against a fake. Also run inside a real lumibot 4.6.23 backtest (`tools/lumibot_gate_backtest.py`, `PandasDataBacktesting`, synthetic daily bars, 2026-10-21): six orders, three refused (over the size limit, off the list, second order on one simulated day). Lumibot received exactly the three allowed ones, ending at 6 SPY = 10 − 5 + 1. The ledger's timestamps were the simulated days |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) (TauricResearch) | Ends with a rating (Buy / Overweight / Hold / Underweight / Sell, or REVIEW) and places nothing | `execute_rating(gate, "NVDA", rating, buy_usd={"Buy": 200}, sell_fraction={"Sell": 1.0})` | Unit tests |

## ai-hedge-fund

```python
from hedge_fund.brokers import PaperBroker
from gate_adapters import GatedHedgeFundBroker, GateRefused

broker = GatedHedgeFundBroker(PaperBroker("book.json"), "gate.json")
# hand `broker` to the fund wherever it takes a Broker
```

- **Refused orders raise `GateRefused`.** The protocol's contract is that an order is either filled completely or raises, so a refusal is never a silent drop. The fund places a cycle's orders one at a time, so a refusal in the middle leaves the earlier orders filled. The fund's own reconciliation then refuses the next session until someone looks.
- **Equity for the daily-loss rule.** The protocol has no equity call, so the adapter values positions at the last price the gate saw for each ticker.
- **What this adds.** The fund already checks position and gross-exposure limits before it places orders, inside its own process. The gate adds limits signed by the account owner, a ledger outside the fund's process, and an audit anyone can run on that ledger.

## lumibot

```python
from lumibot.strategies import Strategy
from gate_adapters import GatedStrategyMixin

class MyBot(GatedStrategyMixin, Strategy):
    gate_config = "gate.json"     # or a dict; rules or a signed mandate
    def on_trading_iteration(self):
        self.submit_order(self.create_order("SPY", 10, "buy"), reason="…")
```

- **Refused orders** are logged with the gate's reasons through `log_message`, and `submit_order` returns `None`. Allowed orders go to lumibot's own `submit_order` unchanged, including its `reason`/`evidence` journal.
- **Price.** The gate checks size against the order's limit price if it has one, otherwise `get_last_price`.
- **Equity** comes from `get_portfolio_value`.
- **Clock.** The gate uses lumibot's `get_datetime`, so in a backtest the daily rules run on simulated days.
- **Sides.** `buy*` counts as buy and `sell*` (including `sell_short`) as sell.
- **Limits.** Multi-leg option orders are checked leg by leg as single orders. That is a known gap; the gate has no notion of a spread.

## TradingAgents

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
import agent_gate, gate_adapters

gate = agent_gate.Gate(agent_gate.load_config("gate.json"))
_, rating = TradingAgentsGraph(config=cfg).propagate("NVDA", "2026-10-21")
gate_adapters.execute_rating(gate, "NVDA", rating, buy_usd={"Buy": 200}, sell_fraction={"Sell": 1.0})
```

- **Nothing trades unless you size it.** A rating places an order only if you map it to a size. "Hold", "REVIEW" (no readable rating) and any rating you leave out place nothing.
- **Sells only reduce a long position,** so a bearish rating never opens a short through this function.
- **The gate checks the sized order like any other.** For example, a $5,000 Buy against a $1,000 limit is refused and logged.

## Still to do

- The lumibot run above used synthetic bars and one broker path (backtesting). It has not been run against a live or paper lumibot broker.
- An MCP proxy, so the gate can sit in front of a trading MCP server (Alpaca's, or a broker's) while the agent keeps that server's other tools. Today `gate_server.py` is a separate MCP server with its own four tools.
