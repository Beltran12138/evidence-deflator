# Signed mandate demo, 2026-10-21

The same gate as the 10-21 demo, now with its rules coming from a signed Trading Mandate (`../MANDATE.md`) instead of the config file. Paper account at Hyperliquid's live mid prices (`sim` broker). The owner key and the gate key are throwaway keys made for this run; neither file is in the repository (`*.key` is ignored).

- Owner (issuer): `0x33b4d1A65Add2D423fac6a4F536A47bF215Ed488`
- Gate key (the mandate's `agent`): `0x1329D66802f3B6e74Ed7C95Ae3d56A8F420782Bb`
- Mandate: BTC and ETH only, $500 largest order, $200 daily loss, 20 orders a day, 14 days (`mandate.json`, hash `10a055318bcb4b6a…`)

The config file (`gate.json`) still lists its own rules; with a mandate set they are ignored.

```
#0   mandate   b7c793604429857a from 0x33b4d1A6… for agent 0x1329D668…, until 2026-11-04T13:20:55Z
#1   BUY  BTC   $   300.00  ALLOWED
#2   BUY  ETH   $ 5,000.00  BLOCKED  <- order is $5,000.00, above the $500 single-order limit
#3   BUY  SOL   $   100.00  BLOCKED  <- SOL is not on the allow list ['BTC', 'ETH']
#4   SELL BTC   $   150.00  ALLOWED
```

`agent-gate audit --config gate.json`:

```
{"ok": true, "lines": 5, "chain_ok": true, "mandates": 1, "orders_allowed": 2, "orders_rechecked": 2, "problems": []}
```

## Why the signatures matter: a forgery the hash chain alone does not catch

The test: change line 2, the refused $5,000 ETH order, to "allowed", then recompute every hash so the chain is consistent again. The plain hash check (`verify`) passes, because anyone can recompute sha256. The audit does not pass:

```
plain hash chain after rewrite: ok = True
audit: ok = false
  line 2: signed by 0xd95e…, not by the mandate's agent 0x1329D668…
  line 2: allowed, but the mandate's rules say no: order is $5,000.00, above the $500 single-order limit
  line 3: signed by 0xf6c0…, not by the mandate's agent 0x1329D668…
  line 4: signed by 0x016c…, not by the mandate's agent 0x1329D668…
```

Before mandates, catching that rewrite needed someone to have kept an earlier head hash. Now the gate key's signature on each line catches it, and so does re-checking each allowed order against the owner's signed limits.

## Check it yourself

```
pip install eth-account
python src/agent_gate.py audit --config docs/gate/demo-2026-10-21-mandate/gate.json
```

The audit reads only `ledger.jsonl`. It needs neither key nor the gate.
