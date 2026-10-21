# Trading Mandate v0

A trading mandate is a short document in which an account owner says, and signs with their own key, what one AI agent may do with their account: which symbols, how large one order may be, how much may be lost in a day, how many orders a day, from when until when. It names the single key allowed to act under it. Anyone holding the gate's ledger can then check, without trusting the gate, that every order the gate let through was inside limits the owner signed.

Status, 2026-10-21: implemented in `src/mandate.py` and `src/agent_gate.py`, covered by `tests/test_mandate.py`. On Hyperliquid testnet, an approveAgent signed by the code here, and an order signed by the gate key, were both parsed by the exchange back to the right addresses. No order has filled yet, because that needs a funded account (see "Hyperliquid" below). v0 is a working format for this project, not a standard anyone else has adopted.

## Why a signed document and not a config file

The gate's earlier rules lived in a JSON file on the machine running the gate. That says what the gate was told. It does not say who told it, and the file can be edited at any time without leaving a trace. A mandate fixes three things a config file cannot:

- **Who authorised the limits.** The signature recovers to the owner's address. On Hyperliquid this is the same address that owns the account.
- **When the limits applied.** `not_before` and `expires` are inside the signed text, and revocation is a second signed message.
- **Which key may act.** The mandate names the gate's key (`agent`). The gate signs every ledger line with that key, so the ledger is attributable to it.

## The document

```json
{
  "type": "trading-mandate",
  "version": "0",
  "id": "8c16bd25a456bd52",
  "issuer": "0xdACbEc130796A8296aDC976f75BE81fe3119E9A5",
  "agent": "0xCacFEb01C434ff92375d1606c954578be3c177DC",
  "venue": "hyperliquid-testnet",
  "account": "0xdACbEc130796A8296aDC976f75BE81fe3119E9A5",
  "scope": {
    "allow": ["BTC", "ETH"],
    "sides": ["buy", "sell"],
    "max_order_usd": 50,
    "max_daily_loss_usd": 20,
    "max_orders_per_day": 10
  },
  "not_before": "2026-10-21T13:13:04Z",
  "expires": "2026-11-04T13:13:04Z"
}
```

| Field | Meaning |
|---|---|
| `issuer` | Address of the owner's Ethereum key. The signature must recover to it. |
| `agent` | Address of the one key allowed to act under the mandate: the gate's key. On Hyperliquid it is also the account's approved API wallet. |
| `venue`, `account` | Where the limits apply: `hyperliquid-testnet`, `hyperliquid-mainnet`, `alpaca`, or `sim`. For Hyperliquid, `account` is the owner's main address. |
| `scope.allow` | Symbols that may be traded. Upper case. |
| `scope.sides` | `buy`, `sell`, or both. An order that only shrinks an existing position is never blocked by this rule. |
| `scope.max_order_usd` | Largest notional of a single order, at the price the gate used. |
| `scope.max_daily_loss_usd` | Once equity is this far below its level at the first ledger line of the UTC day, only orders that reduce a position pass. |
| `scope.max_orders_per_day` | Allowed orders per UTC day. Reducing orders are not counted against it once the limit is reached. |
| `not_before`, `expires` | UTC, `YYYY-MM-DDTHH:MM:SSZ`. Valid from `not_before` up to, but not including, `expires`. |
| `id` | Random. Revocation refers to it. |

The scope fields are the same ones as `agent_gate.check`, the rule function the gate has used since v0. With a mandate in force, the config file's own rule fields are ignored.

## Signing

The owner signs this exact text with EIP-191 `personal_sign`, the "Sign message" every Ethereum wallet offers:

```
Trading mandate v0 (evidencedeflator.com/gate/mandate)
<the document as canonical JSON: keys sorted, no spaces>
```

The signed file is `{"mandate": <document>, "sig": {"scheme": "eip191", "signature": "0x…"}}`. Its identifier is `sha256` of that file as canonical JSON (`mandate_hash`).

v0 uses `personal_sign` and not EIP-712 typed data because every wallet supports it and the text the wallet shows is the document itself. The cost is that wallets show raw JSON rather than labelled fields. The sign page (`/gate/sign/`) puts a labelled preview next to it.

Revocation is a second signed text, `<header>revoke <id> at <UTC time>`, saved next to the mandate as `mandate.json.revoked`. From then on the gate refuses every order under that mandate and records the revocation in the ledger. A revocation signed by anyone other than the issuer is ignored.

## What the gate adds to the ledger

These are the existing hash-chained JSON lines (`docs/gate/`), plus:

- A `mandate` line, the first time a mandate is used. It holds the whole signed mandate, so the ledger needs nothing else to be checked.
- A `revocation` line, the first time a valid revocation is seen.
- On every order line:
  - `mandate_hash`: the mandate the decision was made under;
  - `ctx`: the price, position, loss so far today and orders so far today that the rules were checked against;
  - `gate_sig`: the gate key's EIP-191 signature of `agent-gate ledger line <hash>`. The line's hash already covers the line and every line before it.

`gate_sig` is excluded from the hash, so ledgers written before v0 still verify unchanged.

## Audit: what anyone can check from the ledger alone

`agent-gate audit --config gate.json` (or `agent_gate.audit(rows)`) checks four things:

1. **The hash chain is intact.** No line has been edited, removed from the middle, or reordered.
2. **Every mandate copied into the ledger is valid.** It carries the issuer's signature, and it matches its `mandate_hash`.
3. **Every line from the first mandate on is signed by that mandate's `agent` key.** Rewriting the whole file and recomputing every hash, which defeats a bare hash chain, fails here unless the forger also holds the gate key. `tests/test_mandate.py::test_rewriting_the_whole_file_without_the_gate_key_is_caught`.
4. **Every allowed order is inside the mandate.** It falls inside the time window and before any revocation, and it passes the mandate's rules when `check` is run again on the recorded `ctx`. A gate that logs an over-limit order as allowed is caught even though its signatures are good. `test_a_gate_that_lies_with_its_own_key_is_caught`.

For Hyperliquid, `audit --venue` also asks the exchange for every fill on the account since the ledger began. It lists any order id that no ledger line accounts for. That is the completeness check: the venue, not the gate, says what traded.

## What it does not prove

- **That no order bypassed the gate.**
  - Where the broker holds custody (Alpaca, Robinhood), whoever holds the API key or OAuth token can trade without the gate. The defence is to give the key only to the gate, so the agent never holds one; nothing here can prove that was done.
  - On Hyperliquid, `audit --venue` catches bypassing orders after the fact, because the exchange's fill history is independent of the gate.
- **That the end of the ledger was not cut off.** Deleting the last lines leaves a valid chain. Defences, none built yet:
  - publish the head hash somewhere the gate cannot rewrite, such as a git commit, a post, or an on-chain memo;
  - on Hyperliquid, compare with the venue's fills.
- **That `ctx` was true.** The gate records the price and position it saw. A gate that lies about the price with its own key is not caught by the re-check. It is caught by comparing with the venue's fills, where the venue gives the real fill price.
- **That the agent's trades were any good.** That is the scorecard's job (weekly returns from the same ledger, judged on the site's bar). The mandate only says the agent stayed inside the owner's limits.
- **Anything to a broker.** No broker verifies these signatures today. A mandate is evidence for the owner, an auditor, or a dispute; the broker does not enforce it. On Hyperliquid, part of the authority is enforced by the venue itself, since the API wallet is a separate key the owner can replace (see below).

## Hyperliquid: the gate holds the only key that can trade

Hyperliquid lets a main account approve separate "API wallets" to sign orders for it: "A master account can approve API wallets to sign on behalf of the master account or any of the sub-accounts." It allows "1 unnamed approved wallet and up to 3 named ones", and an approval's "expiration can be at most 180 days in the future". Approving another wallet under the same name deregisters the old one. (Hyperliquid docs, `nonces-and-api-wallets` and the `exchange` endpoint page, read 2026-10-21.)

Whether an API wallet can move funds out: the docs describe the withdrawal flow as requiring "a user wallet signature", and many secondary sources say an API wallet cannot withdraw. I did not find a sentence in the docs that says so outright. Treat it as unverified until it is tested on testnet.

The same docs "strongly" suggest not reusing an API wallet address once it has been deregistered, because "previously signed actions can be replayed once the nonce set is pruned". So use a fresh gate key for each approval: run `keygen` again and draft a new mandate, rather than re-approving an old key.

So the gate's key is approved as the account's API wallet, under the name `gate`:

1. `agent-gate keygen .gate/gate.key` creates the gate's key. Only the gate process reads that file. The agent talks to the gate over MCP and never sees a key.
2. `agent-gate mandate draft --config gate.json --issuer <your address>` prints the text to sign. Sign it with your wallet on `/gate/sign/`, then run `agent-gate mandate attach --sig 0x…`.
3. On the same page, approve the gate's address with your main wallet. The page builds Hyperliquid's `approveAgent` typed data, your wallet signs it, and the page posts it straight to Hyperliquid's API.
4. Set `"broker": "hyperliquid", "network": "testnet", "account": "<your address>", "gate_key": ".gate/gate.key", "mandate": "mandate.json"` in `gate.json`.

Testnet funds: "you need to have deposited on mainnet with the same address. Users who have deposited on mainnet may then receive 1,000 mock USDC for testnet use" (Hyperliquid docs). A fresh address gets `Must deposit before performing actions` back from the exchange.

What was run on 2026-10-21, with throwaway test keys:

- `hl-approve` signed approveAgent for the gate key. The testnet replied `Must deposit before performing actions. User: 0xdacb…`, the test owner's address, so the signature was parsed to the right signer.
- The sign page's typed data, replayed in Python with the wallet on another chain (`signatureChainId` 0xa4b1), recovered the same owner.
- The same data with one field changed recovered a different address (negative control).
- An order signed by the gate key came back `User or API Wallet 0xcacf… does not exist`: the exchange read the gate's address from the signature, and the key is not yet approved for a funded account.

The order also passed through the mandate check first. A $500 order against a $50 limit was refused before reaching the exchange.

## Relation to Google's AP2

AP2 (Agent Payments Protocol, v0.2) has the same structure for payments. A user signs an "open" mandate with constraints whose `cnf` claim names the agent's key. The agent then closes it per transaction "by… generating a Key Binding JWT (Proof-of-Possession) using the key endorsed in the open Mandate's cnf claim". AP2 says "the model could be applied more generally in the future" (ap2-protocol.org, `agent_authorization`, read 2026-10-21). It defines checkout and payment mandates, with constraints such as `payment.amount_range` and `budget`. It has no trading mandate.

| AP2 | Trading Mandate v0 |
|---|---|
| Open mandate (constraints, user-signed) | The mandate document (`scope`, window), signed by `issuer` |
| `cnf` claim: the agent's key | `agent`: the gate's key |
| Closed mandate / Key Binding JWT per transaction | A ledger line signed by `agent`, citing `mandate_hash` |
| SD-JWT verifiable credential | EIP-191 signed canonical JSON |

v0 follows AP2's shape but does not conform to it: no SD-JWT, no selective disclosure, no OpenID4VP flow. Moving to AP2's encoding, as a `mandate.trading` type alongside checkout and payment, is the natural v1 if AP2 opens to other actions. Until then the simpler encoding lets an Ethereum wallet sign it directly and lets Hyperliquid's own key model enforce part of it.

## Versions

- **v0 (this):** EIP-191, one agent key, the five scope fields above, file-based revocation.
- **Candidates for v1,** none started:
  - EIP-712 typed mandates, so wallets show labelled fields;
  - AP2 SD-JWT encoding;
  - publishing the ledger head hash;
  - setting the Hyperliquid approval's own expiry to the mandate's `expires` (approveAgent accepts `valid_until {timestamp}` after the name; the timestamp's unit is not stated, so untested), so the venue enforces the time window too;
  - per-symbol limits;
  - an order-type field once the gate supports more than market orders.
