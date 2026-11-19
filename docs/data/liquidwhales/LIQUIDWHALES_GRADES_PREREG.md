# Pre-registration · Do LiquidWhales' top grades separate skill from luck? (2026-11-19)

## The claim

LiquidWhales grades Hyperliquid wallets S to F and sells copy trading on top. Its tracker FAQ says: "Grades exist precisely so you copy proven, net-of-fees-profitable wallets, not lucky ones." Its method page (`page_how_we_grade.html`, saved here) builds the grade from win rate, a Sharpe-style ratio, drawdown, longevity and round-trip count, with at least 10 closing trades to be rated and 20 round-trips for S. It makes no adjustment for how many wallets the top grades are picked from.

## What we have seen before writing this

Fetched 2026-11-19 09:17–09:18 UTC from the public endpoints that `robots.txt` allows (`/api/pub/`); files and SHA-256 sums in `2026-11-19/`:

- `stats.json`: 611,093 accounts tracked; 28,623 graded (S 3, A 5,815, B 5,778, C 9,389, D 7,638); F 582,275.
- `grades_min_A.json`: the public list for "A and above", 134 wallets (3 S, 131 A), with the site's own grade score, PnL, win rate, Sharpe, drawdown and days active. The endpoint returns at most 200, so this is the top of the 5,818 S+A wallets by the site's score, the same list its leaderboard shows.
- One check by hand while looking for the data: the first S wallet, `0xa6727c…5661`, is a Hyperliquid sub-account (master `0x399965…3336`), from the `userRole` endpoint.

We have not computed our own score for any of these 134 wallets for this test. Four of them are also on our own Hyperliquid boards (`docs/data/hl/latest.json`, 2026-11-16), and one is in the frozen cohort of 2026-10-14, so their full-history t is already public on our site; we checked only the overlap count and did not look those values up before writing this.

## Data and estimator

For each of the 134 wallets: `portfolio` from the Hyperliquid info API on the reading day, then `weekly_returns()` and `score()` from `src/hl_wallet.py`, the same estimator as the wallet check and audit 008. Wallets with fewer than 8 weekly intervals (`MIN_WEEKS`) or that are vaults are counted and left out of the test.

## Primary test (read now, retrospective)

N = 28,623, the graded count. The bar is `bar(28,623)` = t 4.80 (one-sided 2.275%, Bonferroni, as on every Evidence Deflator page). We count how many of the 134 clear it.

- Expectation, written before any score: at most 1 of the 134 clears 4.80.
- **Our critique fails** if 14 or more (≥ 10%) clear the bar. We then say on the audit page that LiquidWhales' top grades do pick out wallets whose records beat the luck bar, in spite of not adjusting for selection.
- Between 2 and 13 we report the count and make no general claim either way.

Reported with no pass mark:
- The same count against `bar(611,093)` = 5.38 (every tracked account) and `bar(134)` = 3.58 (only the published list).
- Spearman between the site's grade score and our t, over the 134.
- How many of the 134 are sub-accounts, and how many share a master (`userRole`, `subAccounts`).
- The three S wallets one by one.

## Secondary test (forward, read 2027-01-14)

The 134 addresses above are frozen by this file. On 2027-01-14 we score only the weeks after 2026-11-19 (`weekly_returns(pf, since=2026-11-19 09:18 UTC)`), needing at least 8 weekly intervals.

- Share of wallets with t_after > 0, with a wallet-resampled 95% interval (10,000 draws, seed 20270114). If the interval lies above 50%, the grades carried forward information; if it includes 50%, they did not show any; if it lies below, they picked wallets that then did worse than a coin flip.
- Spearman(grade score, t_after), same bootstrap. Reported, no pass mark.
- Fewer than 30 wallets with 8 post-freeze weeks: "not enough data", reading moves to 2027-02-11 under the same rules.

## Not tested

- Funding: LiquidWhales does not deduct it and neither does the portfolio PnL series we read, so the two are on the same footing here.
- Copy-trade results: we do not have LiquidWhales' copier fills.
- Grades B to F: the public endpoint does not list them.

## Not done after this file is committed

No change to N, the bar, the estimator, the minimum weeks, the 134 wallets or the cut-offs. Weekly returns of different wallets move together within the same weeks, so the forward interval is likely too narrow; that is stated with the result and not used to move a line.
