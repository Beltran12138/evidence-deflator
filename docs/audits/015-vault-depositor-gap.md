# Audit 015 · What Hyperliquid vault depositors kept of the curve (2026-11-03)

The subject is the vault page's return curve as a promise to depositors, not any one vault.

## Subject

A Hyperliquid vault page shows one curve: the vault's return compounded over time, as if one dollar went in on day one and stayed. Depositors do not hold that dollar. They arrive after good runs, leave after drawdowns, and pay the leader a share of profit. This audit compares the curve with what the vault's own listed depositors made, over the same entry dates.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (live trading) |
| Window | Each depositor's entry date to 2026-11-03 |
| Attempts | Not the question here: the audit is about the gap between a record and what followers of it receive, not about whether the record is luck |

## Finding

**In the 20 large vaults whose curve was positive, depositors kept a median 85% of the curve after the leader's share; in 12 of the 20 they kept less than the curve.** In the 9 vaults with the best curves the median was 78%, and in three of them depositors kept between 23% and 57% of it.

| | Value |
|---|---|
| Vaults examined | 60 largest open vaults by TVL ($148k to $150M) |
| Usable (≥ 20 listed depositors, reliable curve) | 27 |
| Depositors trailed the curve (after fee estimate) | 17 of 27 |
| Median gap, all 27 | −1.3 points |
| Positive-curve vaults: median share of curve kept | 85% (12 of 20 below 100%) |
| Best-curve third (9 vaults): median share kept | 78% |
| Listed depositors who did worse than the curve | 1,024 of 1,876 |
| Dollars: listed depositors' gain vs the curve's gain on the same money | $7.28M vs $11.86M |

- Examples (vault names are the creators' own and unrelated to any firm of the same name): "Citadel", curve +256% after fee, depositors +59%, so 23% kept; "Elsewhere", +595% against +341%, 57%; "Jade Lotus Capital", +307% against +187%, 61%.
- Not every vault: in "Satori Quantum HF Vault" depositors made 2.85 times the curve and in "Long HYPE & BTC | Short Garbage" 1.04 times. Timing can help as well as hurt; on these vaults it hurt more often than it helped.

## How it was computed, and what is uncertain

- Data: Hyperliquid's public `info` endpoint (`vaultDetails`) and the vault list at `stats-data.hyperliquid.xyz/Mainnet/vaults`, fetched 2026-11-03, no key. Script: `tools/vault_follower_gap.py`; raw responses and results in `docs/data/hl/vault-gap/2026-11-03/`.
- Depositor return is money-weighted: all-time PnL in the vault over net money in. The curve return is compounded from each depositor's entry date and dollar-weighted the same way. The leader's profit share (10% on every usable vault) is taken off positive curves as an estimate; Hyperliquid charges it on each depositor's own profit.
- **Lower bound.** `vaultDetails` lists only the largest current depositors (up to 100). Depositors who already left, often after a loss, are missing, so the gap among those listed is the gentler side of the real one.
- **Concentration.** One vault holds 29.5% of the usable depositors' money and $3.0M of the $4.6M dollar gap. The money-weighted gap is −16.8 points with it and −8.4 without it, which is why the headline uses medians, not the money-weighted figure.
- Points and percentages: a vault whose curve rose 300% shows a larger gap in points than one that rose 5% for the same timing behaviour. The share of the curve kept is reported for that reason.
- Curve reconstruction: the all-time history has about a hundred samples. Vaults where more than 10% of intervals carry money movement larger than a quarter of capital are marked unreliable and left out (19 of the 60). 14 had fewer than 20 listed depositors.
- First run 2026-10-18 on the same method: 28 usable, 19 trailed, median −1.4 points, money-weighted −17.7. The 11-03 rerun agrees.

## What it would take

A vault page could show, next to the curve, what its current and former depositors made in aggregate. Hyperliquid has the data; the page does not show it. Until it does, the curve is the return of a depositor who never existed.

Recheck: monthly, same 60-by-TVL rule.
