# Audit 017 · LiquidWhales grades: the S-tier against the luck bar (2026-11-19)

The subject is the S–F grade LiquidWhales publishes for Hyperliquid wallets. No wallet is the subject.

## Subject

LiquidWhales tracks Hyperliquid wallets, grades them S to F and sells copy trading on top. Its tracker FAQ says: "Grades exist precisely so you copy proven, net-of-fees-profitable wallets, not lucky ones." Its method page builds the grade from win rate, a Sharpe-style ratio, drawdown, longevity and round-trip count, with at least 10 closing trades to be rated and 20 round-trips, recent activity, $100k net profit and a Sharpe of 4 for S.

The method page makes no adjustment for how many wallets the top grades are picked from. This audit counts that number and applies the bar.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (live trading) |
| Window | Each wallet's full Hyperliquid history up to 2026-11-19 |
| Attempts | 28,623 graded wallets (611,093 tracked), from LiquidWhales' own public stats. The bar for the best of 28,623 is t = 4.80 |

## Finding

The test was pre-registered and pushed before any wallet was scored (`docs/data/liquidwhales/LIQUIDWHALES_GRADES_PREREG.md`, commit `45665aa`).

**None of the three S wallets, which the site calls its top recommendation for live copy, clears the bar. Of the 88 S and A wallets with enough history to score, 2 do.** Two is inside the pre-registered band where we make no general claim either way.

| | Count |
|---|---|
| Wallets on the public S/A list | 134 (3 S, 131 A) |
| Fewer than 8 weeks of history, not scored | 46 (all A) |
| Scored | 88 |
| Clear t = 4.80 (best of 28,623, pre-registered) | **2** (t 6.47 and 4.82; both A) |
| Clear t = 2 (one wallet picked blind) | 18 |
| S wallets: t | **1.10, 1.44, 2.41** |
| Rank correlation, site grade score vs t | 0.25 |

- **The S tier.** The three S wallets have 24, 135 and 138 weeks of record. Their t values would be ordinary for wallets with no edge. One clears the bar for a single wallet picked blind; none comes near the bar for the best of 28,623.
- **The two that clear** are A wallets ranked in the middle of the list by the site's own score (69 and 84; the median is 72). The grade does not put them on top.
- **Short records.** 46 of the 134 have fewer than eight weeks of history; their median "days active" on the site is 28. The site grades them A. This site does not score them at all.

## One trader, five grades

29 of the 134 listed wallets are Hyperliquid sub-accounts. Five masters each have two or more graded sub-accounts on the list. One master (`0x399965…3336`) has five: the first S wallet and four A wallets. The wallet with the highest t here (6.47) is a sub-account, and a second sub-account of the same master has t 4.12.

A trader who splits one strategy over several sub-accounts can fill several places on a graded list. Counted as one trader, the list is shorter than it looks.

## How it was computed, and what is uncertain

**Data.**
- LiquidWhales' public endpoints (`/api/pub/stats` and `/api/pub/whales`, both allowed by its `robots.txt`), fetched 2026-11-19 09:17–09:18 UTC and saved with SHA-256 sums in `docs/data/liquidwhales/2026-11-19/`.
- Each wallet's `portfolio`, `vaultDetails`, `userRole` and `subAccounts` from Hyperliquid's info API, 09:30–09:55 UTC. Raw responses are kept outside the repository.
- Script: `tools/liquidwhales_test.py`. Results: `docs/data/liquidwhales/2026-11-19/results.json`.

**Estimator.** The one the wallet check uses (`src/hl_wallet.py`): weekly returns from the PnL history over the account value at the start of each week, t on the normal scale, at least 8 weekly intervals.

**Bar.** Best of N = 28,623, the wallets LiquidWhales grades, one-sided 2.275% with Bonferroni, as on every Evidence Deflator page. Against all 611,093 tracked accounts the bar is 5.38, and 1 wallet clears it.

**The list is the top of the grades, not all of them.** The public endpoint returns at most 200 wallets; for "A and above" it returned 134, ranked by the site's score, the same list its leaderboard shows. The other A wallets were not scored.

**Not the same Sharpe.** On the 62 scored wallets with at least 26 weeks, the site's Sharpe is a median 4.25 higher than the one computed here. We do not know how the site computes it. The S rule asks for a Sharpe of 4 or more on the site's scale.

**Funding.** LiquidWhales says it does not deduct funding. Whether Hyperliquid's PnL history, which this audit reads, includes funding was not checked for this audit.

**Level.** The grades are figures from LiquidWhales' own database (L3). The scores here are recomputed from Hyperliquid's chain state (L4).

**What is not tested.** What copiers of these wallets earned: LiquidWhales' copy fills are not public. Grades B to F: the public endpoint does not list them.

**Forward reading.** The 134 addresses are frozen. On 2027-01-14 only the weeks after 2026-11-19 are scored, as pre-registered.

## What it would take

LiquidWhales could show, next to each grade, how many wallets it was picked from and the t the record would need to clear that many candidates by luck alone. It could also count a master and its sub-accounts as one trader.

A grade built from win rate, Sharpe and drawdown ranks records. It does not say whether the best of 28,623 records is better than luck would produce. The FAQ promises the second.

Recheck: on the forward reading, 2027-01-14.
