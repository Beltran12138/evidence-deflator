# Pre-registration · Do platform-style gates already catch what our score catches? (2026-10-20)

Written before anything below is computed. Not blind: the same archived boards and portfolios were used in the retrospective freeze of 2026-10-15 (`../retro/RESULTS.md`), whose pooled result is known to the author (wallets with t_before ≥ 2 had a higher median t_after than the rest). What has not been computed is anything conditional on a platform-style gate.

## Question

Copy-trading and allocation platforms that gate on performance use record length, return and drawdown (Binance copy-trading badges: running days and a drawdown cap; Darwinex DarwinIA: a rating, months of history, return over drawdown). None adjusts for how a record was picked. If a wallet passes such a gate, does our score still separate the ones that do better afterwards from the ones that do worse? If not, a gate built on our score adds nothing a platform does not already have.

## Data

The three archived Hyperliquid boards and the portfolios cached for the retrospective freeze (fetched 2026-10-15), cohorts picked with the same rule (all-time PnL top 100 plus 30-day ROI top 100 among accounts ≥ $10k). For each wallet and snapshot: the record before the snapshot (`truncate`) and after it (`weekly_returns(since=...)`), both with the estimator behind the wallet check. A wallet in several snapshots counts once per snapshot; intervals resample by wallet.

## Gates, on the record before the snapshot

- **G1, copy-trading style** (after Binance's badge rule): at least 30 days of history, cumulative return above zero, and maximum drawdown no deeper than 35%.
- **G2, allocator style** (after Darwinex GOLD): more than 8 months of history, return over the last 52 weeks above 20%, and that return over the maximum drawdown in the same 52 weeks above 2.5.
- **Ours**: t_before ≥ 2 (one record picked blind). Reported alongside: t_before ≥ bar(200) = 3.69, for a record picked from a 200-wallet cohort.

Return and drawdown are on the path that adds up the scored weekly returns (the same path `drawdown()` uses), because most accounts add and withdraw money.

## Outcomes, on the record after the snapshot

- **O1**: t_after (at least 8 weekly intervals).
- **O2**: blow-up, meaning a maximum drawdown of 35% or more after the snapshot (on the same summed path).
- **O3**: summed return after the snapshot.

## Primary test

Among wallets that pass G1, compare those with t_before ≥ 2 against those below 2, pooled over the three snapshots.

- **Our score adds to the gate**: the median O1 of the t ≥ 2 group minus that of the rest is above zero, with a wallet-resampled 95% interval (10,000 draws, seed 20261020) that excludes zero.
- **It adds nothing**: that difference is zero or below.
- Anything else is inconclusive.
- Fewer than 20 wallet-snapshots in either group is "not enough data".

## Secondary, reported with no pass mark

- The same split for O2 (difference in blow-up share) and O3.
- The same split inside G2 (expected to be small).
- Whether G1 itself separates: G1 passers against non-passers on O1 and O2.
- How many of each gate's passers also clear bar(200).

## Limits stated in advance

Wallets' returns are correlated within the same weeks; resampling by wallet does not handle this, so the intervals are likely too narrow. Only wallets with 8 weeks on both sides are scored; who drops out is not random. Both gates are approximations of the platforms' rules on Hyperliquid data, not the platforms' own scores.
