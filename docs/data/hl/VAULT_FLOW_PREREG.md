# Pre-registration · Do vault depositors pay for a credible record? (2026-11-03)

Written before any flow number below has been computed. The two thresholds (θ = 0.10, minimum 300 month-vault observations) were set on 2026-11-03, before the run script was written, and are not changed afterwards. They were proposed by the analyst (sealed before the founder answered, md5 11d4f7d8…) and accepted by the founder; the reasoning: fund flow-performance rank correlations in the literature are roughly 0.2 to 0.3, so a credibility effect beyond raw return of half that size or more would be material. Run on or before 2026-11-10; results go under "Results" without changing anything above that heading.

## Why

The product question is whether a record whose number of attempts is known (registered before trading, every action on a signed ledger) is worth anything to the person deciding where to put money. That only holds if allocators already reward credibility over raw recent return. If deposits chase last month's return and ignore how strong the record is, a certified record gets no more money than a lucky one, and the certification line has no buyer among allocators as they behave today.

Interviews cannot answer this here: the founder's own circle does not allocate to traders, vaults or agents. Hyperliquid vaults record the behaviour directly, so the test reads what depositors did, not what they say.

## Data

- Universe: every vault in `vault-gap/2026-11-03/vaults.json` (9,478 listed, 3,063 open on 2026-11-03), **closed vaults included** so that vaults which lost their depositors are not dropped. HLP and its child vaults are excluded (deposits there follow the protocol, not a leader's record).
- Per vault: `vaultDetails` all-time `accountValueHistory` and `pnlHistory`, fetched on the run day and saved.
- Panel: month-ends t from 2025-01-31 to 2026-09-30. Account value and cumulative PnL are interpolated linearly at t and at t + 30 days.
- A vault is eligible at t if account value at t ≥ $50,000 and it has at least 8 weekly returns up to t (`hl_wallet.weekly_returns`, same estimator as the wallet check). Intervals with heavy money movement are handled as in `tools/vault_follower_gap.py`: vaults whose rough-interval share up to t exceeds 0.10 are left out at that t and counted.

## Variables

- **F (outcome)**: net flow over (t, t + 30d] divided by account value at t, where flow = Δ account value − Δ cumulative PnL. Winsorised at the 1st and 99th percentile within each month.
- **R (raw return)**: curve return over the 30 days before t.
- **S (credibility)**: `hl_wallet.score` t-statistic of the weekly returns from inception to t, the same number the wallet check reports.
- **L (secondary)**: weeks of record up to t.

## Tests

Per month with at least 30 eligible vaults: Spearman correlations, and the partial Spearman correlation of F with S given R (ranks residualised on rank R). Averaged across months; 95% interval from a block bootstrap over months (2,000 draws, seed 20261103).

1. **Positive control (pipeline check)**: mean ρ(F, R) > 0 with the interval above 0. Performance chasing is the best-documented fact about fund flows; if it does not show up here, the flow reconstruction is suspect and no conclusion is drawn from test 2.
2. **Primary**: mean partial ρ(F, S | R).
3. **Negative control**: S shuffled within each month, 1,000 times; the distribution of the primary statistic under shuffling is reported next to the real one.
4. **Secondary, no pass mark**: partial ρ(F, L | R).

## Decision (fixed before the run)

- **Credibility is rewarded**: mean partial ρ(F, S | R) ≥ **θ = 0.10** and the interval's lower end > 0. Then the certification line continues with allocators as the buyer, and the first weekly audit series keeps the "what depositors kept" angle.
- **Not rewarded**: the interval includes 0, or the mean is below θ. Then a certified record would not earn more deposits today; the certification line either finds a buyer that is not an allocator (the rated party itself, a lender, a platform) within two weeks or stops.
- **Minimum sample**: if fewer than 300 month-vault observations are eligible, the test is reported as underpowered and neither branch is taken.

## What this does not test

- Whether allocators would reward a record they were told is certified. No such label exists on Hyperliquid today, so the test measures their current appetite for credibility, not their reaction to the product.
- Leader deposits: the history cannot separate the leader's own money from followers', so a leader topping up after a good month counts as a flow.
- Incentive programmes, points and referral campaigns move deposits for reasons unrelated to the record; they add noise, not a known bias.

## Results

(Empty until the run.)
