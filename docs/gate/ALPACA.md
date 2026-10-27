# Recipe: an AI agent trading an Alpaca paper account through the gate

Goal: an agent in Claude Code can place orders on your Alpaca **paper** account, only inside limits you signed, and every request lands in a ledger the agent cannot rewrite. About 15 minutes.

What has been run: the gate against a live Alpaca paper account from the command line on 2026-10-21 (three orders: one accepted, two refused; `docs/gate/demo-2026-10-21-alpaca/`), and Claude as the agent through the MCP server, with a signed mandate, on a paper account at fixed prices taken from that Alpaca run (`docs/gate/demo-2026-10-21-us/`). This exact sequence, end to end on Alpaca with a mandate, has not been run as written; the steps below are the two runs joined.

The gate's Alpaca broker talks only to `paper-api.alpaca.markets`. There is no live-money switch in this code.

## 1. Install

```bash
pip install "evidence-deflator[mcp,gate] @ git+https://github.com/Beltran12138/evidence-deflator"
```

## 2. Keys: the gate gets them, the agent does not

Create paper keys in the Alpaca dashboard. Put them in the environment of the process that runs the gate, not in a file the agent can read and not in the agent's own environment:

```bash
export APCA_API_KEY_ID=…   APCA_API_SECRET_KEY=…     # PowerShell: $env:APCA_API_KEY_ID = "…"
```

This is the part no code can check for you. Alpaca holds custody; anyone with these keys can trade without the gate. If the agent can see them, the gate is a convention, not a control.

## 3. Config and the gate's own key

```bash
agent-gate init gate.json
agent-gate keygen .gate/gate.key        # the gate signs ledger lines with this; keep it out of git
```

Edit `gate.json`:

```json
{"broker": "alpaca", "state_dir": ".gate", "allow": ["SPY", "QQQ"],
 "gate_key": ".gate/gate.key", "mandate": "mandate.json"}
```

## 4. Your limits, signed

See the starting points, scaled to the paper account's value (candidates, not recommendations):

```bash
agent-gate mandate templates --account-usd 100000
```

Draft one, in your own words for what the agent is for:

```bash
agent-gate mandate draft --config gate.json --issuer 0xYOUR_ADDRESS --template trial --account-usd 100000 \
    --purpose "Try the agent on two index ETFs before giving it anything else" --horizon "One week"
agent-gate mandate examples --config gate.json       # what these limits allow and refuse, as concrete orders
```

Sign the printed text with your wallet's "Sign message" (or on https://evidencedeflator.com/gate/sign/), then:

```bash
agent-gate mandate attach --sig 0x… --config gate.json
agent-gate mandate show --config gate.json
```

Optional, for a platform or reviewer that reads OpenAI's Model Spec vocabulary: `agent-gate mandate scope --config gate.json` prints the same limits as a ScopeOfAutonomy record.

## 5. Give the agent the gate, not the broker

```bash
claude mcp add gate -- agent-gate-mcp --config gate.json
```

Start Claude Code from the shell that holds the Alpaca keys only if the agent's own tools cannot read the environment; otherwise run the gate under a different user or a separate terminal, and connect it as above. If Alpaca's MCP server is also connected, install the Evidence Deflator plugin and set its `direct_order_pattern` option so the agent's direct order calls are refused and sent back to the gate.

Ask the agent to buy $500 of SPY. It calls `place_order`. Ask for $50,000: it gets the refusal and the reason.

## 6. Check what happened, without trusting the gate

```bash
agent-gate log --config gate.json
agent-gate audit --config gate.json      # chain intact, mandate valid, every line signed, every allowed order inside limits
agent-gate scorecard --config gate.json  # the record so far, read the way evidencedeflator.com reads a wallet
```

Compare the ledger with Alpaca's order history in the dashboard. The ledger can show what the gate allowed; only Alpaca's history can show that nothing else traded.

## Stop

- If you signed with a local key file: `agent-gate mandate revoke --key <your key file> --config gate.json`. From then on every order is refused and the revocation is in the ledger.
- If you signed with a wallet: the sign page has no revocation button yet. A revocation is the text `Trading mandate v0 (evidencedeflator.com/gate/mandate)` on one line and `revoke <mandate id> at <UTC time>` on the next, signed by the same address and saved as `mandate.json.revoked` in the form `{"revoke": "<mandate id>", "ts": "<UTC time>", "signature": "0x…"}`; there is no command that attaches a wallet signature to it yet.
- Either way, removing the gate's MCP server or rotating the Alpaca keys stops the agent at once.
