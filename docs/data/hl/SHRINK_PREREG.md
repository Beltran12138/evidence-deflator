# Pre-registration · Does shrinking toward all wallets beat the raw score? (2026-11-10)

Applies to the frozen cohort `cohort-2026-10-14.json` (200 wallets, frozen 2026-10-14 09:48 UTC). Reading on 2026-12-09, together with test 2 and the ordering test (`COHORT_PREREG_ORDERING.md`). Results go under "Results" without changing anything above that heading.

## Why

The site answers "could this record be luck?" with bars: 2 for one record picked blind, 4.90 for the best of a board. A wallet on a leaderboard is there because its record looks good, so its own numbers over-state it (the winner's curse), and a yes/no bar says nothing about by how much. Empirical Bayes gives a number instead: estimate how true skill is spread across all wallets, then pull each wallet's estimate toward that spread by as much as its record length warrants. The claim to test is that this shrunk estimate predicts a wallet's later record better than the raw estimate, and orders wallets no worse. If it does not, it does not go on the site.

## Timing and what we have seen

Written 2026-11-10, 27 days after the freeze and before anything below has been fetched or computed. No post-freeze score has been computed by our tools for any cohort wallet. The daily Hyperliquid board shows full-history t for cohort wallets still on it, which includes post-freeze weeks; we have not used it for this test. The model code (`src/shrink.py`) and the script (`tools/shrink_test.py`, both modes) are committed with this file, and have only been run on simulated data (`tests/test_shrink.py`).

## Model

For wallet i, `z_i` is the site's score (`hl_wallet.score`, t on the normal scale) and `y_i` its record length in years. Take `z_i ~ Normal(s_i · √y_i, 1)`, with `s_i` the wallet's true annual Sharpe. The spread `g` of `s` across wallets is estimated by nonparametric maximum likelihood on a grid from −6 to 6 in steps of 0.1 (EM, at most 500 iterations), no shape assumed. Each cohort wallet's shrunk estimate is its posterior mean of `s`; its raw estimate is `z_i / √y_i`. Records of unequal length are handled by the likelihood, which is why this is used rather than Tweedie's formula with one noise level.

## Data, fixed now (`freeze`)

- **Population sample**: the public leaderboard fetched on the run day; addresses de-duplicated, lower-cased and sorted; 1,500 drawn with `random.Random(20261110).sample`. Each portfolio is cut at the freeze (samples after `frozen_at_ms` dropped) and scored as above; wallets without a score (fewer than 8 intervals) are left out and counted. `g` is fitted on the rest.
- **Cohort**: each of the 200 portfolios cut at the freeze the same way, giving `z_before`, `y_before`, raw and shrunk estimates. `z_before` is recomputed rather than taken from the frozen file, so raw and shrunk come from the same series; agreement with the stored `t_before` is reported.
- Both are saved to `shrink/prior.json` and `shrink/estimates.json` and committed before 2026-12-09. Those files are the predictions; they are not rewritten.

## Reading on 2026-12-09 (`read`)

For each cohort wallet with an estimate: `z_after`, `y_after` from `weekly_returns(pf, since=frozen_at_ms)` + `score()`, at least 8 intervals, fetched on the reading day (the same forward score as the ordering test). Errors on the forward score's own scale: `e_raw = z_after − raw · √y_after`, `e_shrunk = z_after − shrunk · √y_after`. Intervals below are 95%, resampling wallets (10,000 draws, seed 20261209).

- **P1 (primary), prediction**: D = mean(e_raw²) − mean(e_shrunk²). Positive means the shrunk estimate predicts better.
- **P2 (binding), ordering**: Δρ = Spearman(shrunk, z_after) − Spearman(z_before, z_after).

## Decision

- **Ship** (wallet page shows "this record claims X; across all wallets, about Y is believable, interval …"): D's interval excludes 0 above, and Δρ's interval does not lie wholly below 0. If Δρ's interval also excludes 0 above, the shrunk estimate may replace raw t for ranking; otherwise ranking stays as it is.
- **Predicts worse**: D's interval wholly below 0. Do not ship; the record page says so.
- **Predicts better but ranks worse**: D above 0, Δρ wholly below 0. Do not ship.
- **Anything else is inconclusive**: do not ship; read once more on 2027-02-03 with the same frozen estimates and the same rules, then stop either way.
- Fewer than 30 wallets with both an estimate and a forward score is "not enough data"; the reading moves to 2027-01-06 under the same rules.

## Reported with no pass mark

Mean error of each (raw over-states if mean(e_raw) < 0); Spearman of raw Sharpe against `z_after`; coverage of each wallet's 90% predictive interval for `z_after` (from its posterior plus unit noise); the fitted spread's mean, sd and quantiles; median share shrunk for wallets with `t_before` ≥ 2 against the rest.

## Known limits, stated with the result and not used to move a line

- **Correlation.** Wallets trade the same markets in the same weeks, so forward errors share a common shock. Wallet resampling ignores that, so the intervals are likely too narrow, and the posterior intervals treat each wallet's noise as its own. Winner's-curse corrections are known to be biased under dependence (Biostatistics 26(1), kxaf025, 2025).
- **Population.** "All wallets" means accounts on Hyperliquid's public leaderboard, not every address.
- **Short reading.** Eight weeks of forward record is little; P1 is chosen as primary because it pools error across wallets, where an ordering test at eight weeks has little power.

## Not done

No change of model, grid, sample, seed, estimator, minimum length or subset after this file is committed.

## Results

### Freeze run, 2026-11-10 (before any forward score)

`tools/shrink_test.py freeze`, committed with `shrink/prior.json` and `shrink/estimates.json`. These two files are the predictions.

- Leaderboard: 48,073 accounts; 1,500 sampled, 0 failed to fetch, 1,138 with a score up to the freeze (median record 0.72 years).
- Raw scores in the sample lean positive: 60.3% have z > 0, median raw annual Sharpe 0.49, 5.1% at z ≥ 2 and 4.7% at z ≤ −2. The fitted spread has mean 0.31, sd 0.90, and puts 81% of its mass above 0, most of it between 0.5 and 0.8, with a smaller lump near −1.2 (NPMLE fits are lumpy by construction). EM stopped at its 500-iteration cap.
- ⚠ Read: the shrinkage target sits above zero. The likely cause is who is in the sample, not a coding error: the leaderboard lists accounts that still exist, and weeks starting below $1,000 of account value are not scored, so accounts that were wiped out contribute less of their losing record. This is stated here, after seeing the fit and before any forward score; under the rules above, nothing is changed. If shrinkage loses on 2026-12-09, this is the first candidate cause, and a fix would need a new pre-registration.
- Cohort: 180 of 200 have an estimate (20 without 8 intervals before the freeze). Recomputed `z_before` against the stored `t_before`: Spearman 0.979, median absolute difference 0.034, 36 differ by more than 0.1. Median share shrunk: 59% for wallets with stored `t_before` ≥ 2 (18 wallets), 45% for the rest.
