"""Run GatedStrategyMixin inside a real lumibot backtest (PandasDataBacktesting, synthetic daily bars).

    pip install lumibot   # in a separate venv; it pulls many dependencies
    LUMIBOT_DISABLE_DOTENV=1 python tools/lumibot_gate_backtest.py src

Run 2026-10-21 with lumibot 4.6.23; result in docs/gate/INTEGRATIONS.md.
"""
import json
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd

sys.path.insert(0, sys.argv[1])  # decision-confidence/src
import agent_gate as ag  # noqa: E402
import gate_adapters as ga  # noqa: E402

from lumibot.backtesting import PandasDataBacktesting  # noqa: E402
from lumibot.entities import Asset, Data  # noqa: E402
from lumibot.strategies import Strategy  # noqa: E402

STATE = tempfile.mkdtemp(prefix="lb-gate-")
CFG = dict(ag.DEFAULTS, state_dir=STATE, allow=["SPY"], max_order_usd=1500, max_daily_loss_usd=10_000,
           max_orders_per_day=1)

idx = pd.date_range("2025-01-02 16:00", periods=40, freq="B", tz="America/New_York")
px = [100 + 0.5 * i for i in range(len(idx))]
df = pd.DataFrame({"open": px, "high": [p + 1 for p in px], "low": [p - 1 for p in px], "close": px,
                   "volume": 1_000_000}, index=idx)
spy, qqq = Asset("SPY"), Asset("QQQ")
pandas_data = {spy: Data(spy, df, timestep="day"), qqq: Data(qqq, df.copy(), timestep="day")}


FINAL = {}


class GatedBot(ga.GatedStrategyMixin, Strategy):
    gate_config = CFG

    def initialize(self):
        self.sleeptime = "1D"
        self.step = 0

    def on_trading_iteration(self):
        plan = {0: ("SPY", 10, "buy"), 1: ("SPY", 100, "buy"), 2: ("QQQ", 5, "buy"), 3: ("SPY", 5, "sell")}
        if self.step in plan:
            sym, q, side = plan[self.step]
            self.submit_order(self.create_order(sym, q, side), reason=f"step {self.step}")
        if self.step == 4:  # two orders on one simulated day: the second hits max_orders_per_day=1
            self.submit_order(self.create_order("SPY", 1, "buy"), reason="step 4a")
            self.submit_order(self.create_order("SPY", 1, "buy"), reason="step 4b")
        self.step += 1

    def on_strategy_end(self):
        FINAL["positions"] = {p.asset.symbol: float(p.quantity) for p in self.get_positions() if p.asset.symbol != "USD"}
        FINAL["orders_seen_by_lumibot"] = len(self.get_orders()) if hasattr(self, "get_orders") else None


if __name__ == "__main__":
    GatedBot.backtest(PandasDataBacktesting, datetime(2025, 1, 2), datetime(2025, 2, 20), pandas_data=pandas_data,
                      show_plot=False, show_tearsheet=False, save_tearsheet=False, show_indicators=False,
                      save_logfile=False, quiet_logs=True)
    rows = ag.Ledger(os.path.join(STATE, "ledger.jsonl")).read()
    print("GATE LEDGER")
    for r in rows:
        print(ag._fmt(r))
    print(json.dumps(ag.verify_chain(rows)))
    print("LUMIBOT FINAL", FINAL)
