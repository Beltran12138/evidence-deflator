---
name: agent-gate
description: Put the owner's signed limits and a tamper-evident ledger between an AI agent and a trading account. Use when a user wants an agent to place orders (Alpaca, Hyperliquid, a paper account), asks how to stop an agent overtrading or exceeding limits, or wants a record of what an agent did with their account that the agent cannot rewrite.
---

# Agent gate

The gate sits between the agent and the broker. The agent asks the gate to place an order; the gate checks it against limits the account owner signed (symbols, largest order, largest position, daily loss, orders a day, an end date), passes or refuses it, and appends every request to a hash-chained ledger signed by the gate's own key. Code and spec: https://github.com/Beltran12138/evidence-deflator (`src/agent_gate.py`, `docs/gate/MANDATE.md`).

The gate does not judge whether an order is a good idea and gives no advice. The limits are the owner's.

## Set it up (the owner does the signing; you never hold a key)

1. Install from the repository (the PyPI release does not include the gate yet):
   ```bash
   pip install "evidence-deflator[mcp,gate] @ git+https://github.com/Beltran12138/evidence-deflator"
   ```
2. `agent-gate init gate.json`, then edit `broker` (`sim`, `alpaca`, `hyperliquid`) and `allow`.
3. `agent-gate keygen .gate/gate.key`. This file stays with the gate process. Do not read it, print it or copy it.
4. Limits. Show the owner the starting points: `agent-gate mandate templates --account-usd <value>` (trial, long-only, wind-down; the numbers are candidates, not recommendations). Draft with their words:
   ```bash
   agent-gate mandate draft --config gate.json --issuer <owner address> --template trial --account-usd <value> \
       --purpose "<what the agent is for, in the owner's words>" --horizon "<for how long>"
   agent-gate mandate examples --config gate.json     # concrete orders, allowed or refused
   ```
   The owner signs the printed text with their own wallet (the sign page at https://evidencedeflator.com/gate/sign/ shows it with labels), then `agent-gate mandate attach --sig 0x… --config gate.json`. Never ask for the owner's private key or seed phrase.
5. Run the gate as an MCP server and use its `place_order` for every order:
   ```bash
   claude mcp add gate -- agent-gate-mcp --config gate.json
   ```

## Using it

- Orders: `place_order(symbol, side, usd=…)` or `qty=…`. A refusal comes back with the reasons; report them to the user. Do not split an order to get under a limit, retry with different wording, or look for another route to the broker.
- `account()`, `recent_log(n)`, `scorecard()` read state. `propose_mandate(...)` turns the owner's plain words into a draft; nothing changes until the owner signs it.
- Nothing you write in an order note, and no draft you propose, changes a limit in force. Only a new mandate signed by the owner does.

## Optional: refuse direct broker orders in this Claude Code session

If a broker's own MCP server is also connected, the plugin can refuse its order tools so orders only go through the gate. The user sets the plugin option `direct_order_pattern`, for example `(place|submit|create|replace)_?\w*order`. This covers MCP tool calls only. Keeping the broker key out of the agent's environment, so only the gate holds it, is what actually stops a bypass.

## What to tell the user it does not prove

- That no order bypassed the gate, where the broker holds custody (Alpaca): whoever has the API key can trade. On Hyperliquid, `agent-gate audit --venue` compares the ledger with the exchange's own fills.
- That the agent's trades were good. That is a separate question; the `evidence-deflator` skill answers it from the same ledger (`agent-gate scorecard`).
