# deflatedT entries in ERC-8004

Evidence Deflator writes its reading of a trading agent's record into the ERC-8004 reputation registry
(`0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`, v2.0.0) from one address:

**`0xF02cF39d6b91Ac62B1D21d0F1C39335118c1F9A1`**

Anyone can write feedback in ERC-8004, so only entries from this address are ours. Each entry is
`giveFeedback(agentId, value, 2, "deflatedT", tag2, endpoint, feedbackURI, feedbackHash)`: `value / 100`
is t from the wallet check's estimator, `tag2` is `bestOf<N>` when the agent was picked from a field of N
or `single`, and `feedbackHash` is keccak256 of the evidence file at `feedbackURI`, which records the
Hyperliquid response it was computed from (`portfolio.json` beside it). Built by `tools/erc8004_evidence.py`.

| Date | Chain | Agent | t | tag2 | Window | Transaction |
|---|---|---|---|---|---|---|
| 2026-10-17 | Base (8453) | DegenAI, agentId 19136 | 1.33 | single | from 2026-02-05 (first registration), 35.7 weeks | `0xeaedbc13bf17a7cbd30c7509825217691aa2669d44a8637fb2379f9bb401a385` (block 52746882) |
| 2026-10-17 | Ethereum (1) | DegenAI, agentId 23121 | 1.33 | single | same | `0x716b5e99cce13a5b7d0190f9b6c02923aafd02168e77016def8f266647f7d8f7` (block 26215849) |

DegenAI was the only agent found, among about 9,300 registrations checked on Ethereum, Base and Arc on
2026-10-17, that states it trades Hyperliquid perps, binds a Hyperliquid wallet on-chain and has at least
eight weeks of record. Its record since registration made money; t = 1.33 cannot be told apart from luck.
