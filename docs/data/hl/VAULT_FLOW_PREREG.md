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

## Amendment 1 (2026-11-03, before any outcome was computed)

**What changed.** The rough-interval rule in "Data" (leave a vault out at t if more than 10% of its intervals up to t carry money movement larger than a quarter of capital) no longer applies to the primary test. The primary test uses every vault that meets the other eligibility rules. The original rule is kept as a sensitivity run, reported next to the primary one with the same statistics; the decision is taken on the primary run only. Nothing else changes: θ = 0.10, the 300-observation minimum, the 30-per-month minimum, both controls, the seed and the deadline.

**What was seen before the change.** Only eligibility counts, no correlation of any kind. A smoke test of `tools/vault_flow_test.py` on the first 127 fetched vaults gave 3 eligible month-vaults out of 2,667 (2,380 below $50k, 263 outside the vault's history, 14 rough, 7 under 8 weeks). On the 52 normal vaults among the 60 largest (details already saved under `vault-gap/2026-11-03/details/`), the rule left out 365 of the 557 month-vaults that met the size and 8-week rules, leaving 192, with at most 24 in any month: below both minimums. Without the rule the same vaults give 557, 40 to 51 a month; with the threshold at 0.25 instead of 0.10, 472.

**Why.** The rule was carried over from the depositor-gap tool, where it protects a curve reconstruction. Here the outcome is the flow itself, and the rule removes exactly the vaults whose money moved most: it selects on something close to the outcome, which would bias the test toward finding no effect, and it would leave the test underpowered by construction. F is computed from account value and PnL at two interpolated points and does not depend on the curve; R and S are noisier for rough vaults but not biased in a known direction.

**Also recorded.** The fetch skips vaults created after 2026-08-05: they cannot have 8 weeks of record by the last month-end (2026-09-30), so they could never be eligible. This removes no observation.

## Results

Run 2026-11-04 with `tools/vault_flow_test.py` on `vault-flow/2026-11-03/histories.jsonl` (9,459 vaults: every normal vault created by 2026-08-05; fetched 2026-11-03 to 11-04, no failures left, no duplicates). Full output in `vault-flow/2026-11-03/results.json`.

**Decision: no conclusion. The positive control failed.** Mean ρ(F, R) = 0.045, 95% interval −0.002 to 0.091: the interval touches 0, so the pre-registered pipeline check is not passed and test 2 is not read for a decision.

| Primary run (Amendment 1) | Value |
|---|---|
| Eligible month-vaults | 1,561 (all 21 months used, 33 to 97 a month) |
| Left out | 175,157 below $50k, 21,396 outside the vault's history, 525 under 8 weeks |
| ρ(F, R), positive control | 0.045 [−0.002, 0.091] |
| Partial ρ(F, S \| R), primary | 0.030 [−0.020, 0.085] |
| Shuffle control for the primary | median −0.001, 95% range −0.055 to 0.053; 13% of shuffles at or above 0.030 |
| Partial ρ(F, L \| R), secondary | 0.027 [−0.010, 0.070] |

Reported as fixed, not as a decision: had the control passed, the primary would have read "not rewarded" (0.030 < θ = 0.10, interval includes 0), and the upper end of its interval (0.085) is below θ.

Sensitivity run (original rough rule): 375 month-vaults in the 9 months that reach 30 vaults, all from 2026-01 on. ρ(F, R) = −0.015 [−0.143, 0.093], control also failed; partial ρ(F, S | R) = −0.133 [−0.209, −0.060], outside its shuffle range (99.3% of shuffles at or above it). It points the other way from the primary run and rests on a quarter of the sample and the vaults with the least money movement.

**Exploratory, after the result (does not change the decision).** To see why the control failed: flows do not track past return at longer horizons either (mean ρ with 90-day return −0.013, with 180-day return −0.014; 30-day 0.045, positive in 15 of 21 months). Samples in the 90 days before t are a median 7 days apart (90th percentile 14), so the 30-day return rests on about four intervals. Two readings remain open and this data cannot separate them: deposits into Hyperliquid vaults do not follow past performance, or the flow reconstruction (account value minus PnL, interpolated, leader's own money included) is too noisy to show it. The test that separates them is to compare the reconstructed F with exact deposits and withdrawals from each vault's ledger.
