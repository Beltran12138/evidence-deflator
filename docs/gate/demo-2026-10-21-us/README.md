# From one sentence to a signed mandate, an agent's orders, an attestation and a panel (2026-10-21 UTC)

The whole loop on a US-stock paper account, with Claude as the agent. Paper account (`sim` broker) at fixed prices taken from the Alpaca paper run earlier the same day (`../demo-2026-10-21-alpaca/`): AAPL 339.66, SPY 770.72, TSLA 379.83. Both keys (owner and gate) are throwaway test keys made for this run; neither is in the repository. The developer played the owner.

1. **The owner says the limits in plain Chinese.** Claude, with only the gate's MCP server attached, called `propose_mandate`. The gate turned the scope into seven worked examples by code (`src/mandate_examples.py`), and Claude listed them for confirmation and asked five questions about what the words left open (short selling, whether the daily loss counts unrealised losses, cost or market value for the position limit, which midnight, whether a stop-loss sell uses one of the 20 orders). Owner's words, Claude's reply, the draft: `agent-replies.md` (run 1), `proposals/20261021T181638Z.json`, `mandate.json.unsigned.json`.
2. **The owner signs.** `agent-gate mandate sign --key owner.key` (a wallet user signs the same text at evidencedeflator.com/gate/sign, which shows the same seven examples, each with a box to tick, before the sign button works). Signed: `mandate.json`, hash `8444f1aa3d89ff6a…`.
3. **Claude trades through the gate.** Asked for $300 of Apple, $5,000 of SPY at once and $100 of Tesla: AAPL allowed and filled; SPY refused (over the $500 single-order limit and the $2,000 position limit); TSLA refused (not on the list). Claude's reply, verbatim in `agent-replies.md` (run 2): 「SPY 我不会拆成多笔小单来绕开上限。」 Ledger: `ledger.jsonl`.
4. **Audit and attestation.** `agent-gate audit`: ok, 4 lines, chain intact, one mandate, the one allowed order re-checked against the signed limits. `agent-gate attest` wrote `attestation.json`, signed by the gate key the mandate names and bound to the ledger's head hash. `agent-gate verify-attestation attestation.json` recomputes every number from the ledger: ok. Changing one count in the attestation makes it fail on both the signature and the count.
5. **Panel.** `agent-gate panel` over this gate, the Alpaca paper gate and the Hyperliquid paper gate: `panel.html`, read from the three ledgers alone.

One defect found and fixed during the run: in run 1 Claude reported "the rules in force allow BTC/ETH/SOL". With a mandate configured but not yet signed, the gate already refused every order, but the `account` tool showed the config file's default rules. It now says no rules are in force until the owner signs (test: `test_account_tool_says_no_rules_before_the_mandate_is_signed`).

Check it yourself (no keys needed):

```
python src/agent_gate.py verify-attestation docs/gate/demo-2026-10-21-us/attestation.json --config docs/gate/demo-2026-10-21-us/gate.json
python src/agent_gate.py audit --config docs/gate/demo-2026-10-21-us/gate.json
python src/mandate_examples.py --scope docs/gate/demo-2026-10-21-us/mandate.json
```
