# Pre-registration · Is the ruler calibrated? (2026-10-21)

Written before any of the numbers below have been computed. Run on or before 2026-12-09, results added under "Results" without changing anything above that heading.

## Why

Every verdict on the site rests on one claim: with no skill, a record reaches t ≥ 2 about 2.275% of the time, whatever its length, and t ≥ bar(n) about 2.275% of the time for the best of n. The 12-09 cohort reading asks whether the ruler *orders* wallets (`COHORT_PREREG_ORDERING.md`). It cannot tell us whether the ruler is *calibrated*: eight weeks is too short for that (a single-test pass in eight weeks needs an annual Sharpe of about 5). This file tests calibration directly, on real return series, without waiting.

A plain count of how many ordinary wallets pass would not do: an excess could mean the ruler is too loose or that some of them are skilled, and a shortfall could mean the ruler is too strict or that fees drag everyone down. So the primary test removes skill by construction.

## Data

The 200 wallets of `cohort-2026-10-14.json`. For each, the portfolio is fetched on the run day and turned into weekly returns with `hl_wallet.weekly_returns` (same estimator as the wallet check). Wallets with fewer than 8 weekly intervals are left out and counted.

## Test 1 (primary): sign-flip placebo

For each wallet, multiply each weekly return by an independent random sign (±1, probability ½), demean nothing, and score with `hl_wallet.score`. This keeps each wallet's volatility, fat tails and record length and sets its true mean to zero. Repeat 200 times (seed 20261021). Pass rate = share of (wallet, draw) pairs with t ≥ 2.

- Nominal: 2.275%.
- **Anti-conservative**: pass rate > 4.55% (twice nominal). Then the wallet verdicts and the gate stop being described as calibrated, the page says so, and the estimator is fixed before any further verdict is published.
- **Conservative**: pass rate < 1.14% (half nominal). Reported on the method page; no change to verdicts, since erring strict is the documented intent.
- In between: calibrated.

Also reported, no pass mark: the same pass rate split by record length (8–25, 26–51, 52+ weeks), and the rate at t ≥ 3.5 against its nominal 0.0233%.

## Test 2: power on a planted edge

Same flipped series, plus a constant weekly drift sized so that each wallet's true annual Sharpe is 2 (drift = 2 / √52 × the wallet's weekly standard deviation). Detection rate at t ≥ 2 is compared with the rate the normal approximation predicts for that wallet's length, Φ(2 × √(weeks/52) − 2), averaged over wallets.

- Reported as detected / predicted. Below 0.7 means the ruler misses real edges more often than it claims; the method page then states the measured power next to the claimed one. No change to verdicts.

## What this does not test

Leakage. A record built with look-ahead passes any test on its returns (arXiv 2608.27734 shows a leaky oracle at Sharpe 35 clearing deflated Sharpe and PBO). Public wallets cannot look ahead in the way a backtest can, which is one reason the site scores public records rather than submitted backtests.

## Results

(not yet run)
