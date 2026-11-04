# Pre-registration · Vault flow test, version 2: exact flows (2026-11-04)

Written after version 1 (`VAULT_FLOW_PREREG.md`) was run and before any exact flow below has been fetched or computed. Version 1 ended with no conclusion: its positive control failed (ρ(F, R) = 0.045 [−0.002, 0.091]), and it could not tell whether Hyperliquid vault deposits ignore past performance or whether its flow reconstruction (account value minus PnL, interpolated between samples about a week apart, the leader's own money included) was too noisy to show it. Version 2 measures flows exactly and separates the two. Run on or before 2026-11-10; results go under "Results" without changing anything above that heading.

What was looked at before writing this: version 1's results (above, and in its file), and the field names of one page of `userNonFundingLedgerUpdates` for the HLP vault address (event types `vaultDeposit` and `vaultWithdraw`; withdrawals carry `user`, `requestedUsd`, `netWithdrawnUsd`, `commission`, `closingCost`, `basis`; deposits carry only `vault` and `usdc`, no depositor). No flow from that page was summed or compared with anything.

## Data

- **Universe**: the month-vaults eligible in version 1's primary run (account value ≥ $50,000 at t, at least 8 weekly returns up to t; 1,561 month-vaults over 21 months), unchanged. R, S and L are taken from version 1 unchanged.
- **Vault ledger**: `userNonFundingLedgerUpdates` with `user` = the vault address, paged by `startTime` (2,000 events a page) from 2025-01-01 to 2026-10-31, fetched on the run day and saved.
- **Leader ledger**: the same call with `user` = the vault's leader (from the saved vault list), to find the leader's own deposits into that vault, because the vault's own deposit events do not name the depositor.

## Variables

- **F_all (exact, all money)**: over (t, t + 30d], the sum of `usdc` in the vault's `vaultDeposit` events minus the sum of `requestedUsd` in its `vaultWithdraw` events, divided by account value at t.
- **F\* (exact, followers only)**: as F_all, minus the leader's own deposits into this vault (from the leader ledger, events with `vault` = this vault) and minus nothing for the leader's withdrawals, which are dropped by `user` = leader. Winsorised at the 1st and 99th percentile within each month, as in version 1.
- R, S, L: as in version 1.

## Step 1 · Does the version 1 reconstruction measure flows?

Spearman correlation, pooled over all month-vaults, between version 1's F and F_all (both include the leader's money, so this checks the reconstruction alone).

- ρ ≥ 0.7: the reconstruction measured flows; version 1's failed control then reflects behaviour, not measurement.
- ρ < 0.7: it did not; version 1 is set aside and only version 2 is read.

Reported either way; it does not gate step 2.

## Step 2 · The test, on exact follower flows

Version 1's tests with F\* in place of F: per month with at least 30 vaults, ρ(F\*, R) and partial ρ(F\*, S | R) and partial ρ(F\*, L | R); means across months; 95% intervals from a bootstrap over months (2,000 draws, seed 20261104); S shuffled within month 1,000 times as the negative control.

## Decision (fixed before the run)

- **Positive control passes** (ρ(F\*, R) interval above 0): read the primary as in version 1. Partial ρ(F\*, S | R) ≥ θ = 0.10 with the interval above 0 → **credibility is rewarded**; otherwise → **not rewarded**.
- **Positive control fails and step 1 gave ρ ≥ 0.7**: on exact flows, deposits do not follow past performance. Then neither return nor record strength moves money into these vaults, and a certified record would not attract deposits either → treated as **not rewarded** for the product decision, and stated as its own finding ("Hyperliquid vault deposits did not follow 30-day performance, 2025-01 to 2026-09").
- **Positive control fails and step 1 gave ρ < 0.7**: no conclusion; the question is left open and no third version is run on vault data.
- **Not rewarded**, as in version 1: the certification line finds a buyer that is not an allocator (the rated party itself, a lender, a platform) within two weeks or stops.
- Fewer than 300 month-vaults with a complete ledger: underpowered, no branch taken.

## What this does not test

- The same limits as version 1: no "certified" label exists, so this measures today's appetite for credibility, not the reaction to a product.
- Leader money moved through another address the leader controls is counted as follower money.
- Withdrawal amount is `requestedUsd` (what leaves the vault's equity before the leader's commission and closing cost are settled); with commission at 10% of profit this can overstate outflows slightly in profitable months.

## Results

(Empty until the run.)
