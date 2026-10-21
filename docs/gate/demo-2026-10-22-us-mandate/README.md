# Signed mandate for a US-stock paper account, 2026-10-22 (deck v10, slide 03)

A Trading Mandate v0 (`../MANDATE.md`) for an Alpaca paper account: AAPL and SPY only, buy and sell, $500 largest order, $2,000 largest position per symbol, $200 daily loss, 20 orders a day, 14 days. Both keys are throwaway test keys made for this file; neither is in the repository.

- Owner (issuer): `0x3c5e32116F83d0316fe7315499c75b82cE43d94D`
- Gate key (the mandate's `agent`): `0x342F62CC6f2d5177162768ecb232f775B924746f`
- Mandate hash: `ec35110e0981f6f3…`

No orders have been placed under this mandate. The orders on slide 02 are the 10-21 Alpaca paper run (`../demo-2026-10-21-alpaca/`), which used the config-file rules. The signed-ledger audit, including the forgery it catches, is shown on the Hyperliquid paper run (`../demo-2026-10-21-mandate/`).

Check the signature:

```
python -c "import sys,json; sys.path.insert(0,'src'); import mandate as M; print(M.verify(M.load('docs/gate/demo-2026-10-22-us-mandate/mandate.json')) or 'ok')"
```
