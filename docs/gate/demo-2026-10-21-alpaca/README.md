# Agent gate · Alpaca paper account, 2026-10-21

The gate with `"broker": "alpaca"` against a live Alpaca paper account (keys from the environment, not stored here). Three orders, placed from the command line before the US open:

- line 0: AAPL buy $300 — inside the rules, sent to Alpaca, status `accepted` (a pre-market market order fills at the open).
- line 1: SPY buy $5,000 — refused, above the $500 single-order limit.
- line 2: TSLA buy $100 — refused, not on the allow list.

Prices are Alpaca's latest trades at the time. Check the chain: `python src/agent_gate.py verify --config docs/gate/demo-2026-10-21-alpaca/gate.json`.
