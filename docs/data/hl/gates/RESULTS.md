# Platform-style gates: results (2026-10-20)

Rule declared in [PREREG.md](PREREG.md) and committed (ae45ca0) before anything below was computed. Not blind: same archived boards and cached portfolios as the [retrospective freeze](../retro/RESULTS.md). Script: `tools/gate_test.py`. Raw output: [results.json](results.json).

405 wallet-snapshots (269 wallets) have 8 weeks or more on both sides of a snapshot, the same set the retrospective freeze scored.

## Primary: **not enough data**

Only 19 of the 405 pass G1 (30 days, positive summed return, drawdown no deeper than 35%): 7 with t_before ≥ 2 and 12 below. The rule needed 20 in each group. For the record, the 7 had a median t_after of 1.01 against 0.68, and 1 of 7 blew up afterwards against 8 of 12; the intervals are wide.

G1 passes so few because drawdowns on Hyperliquid's top boards are deep: the median deepest fall before the snapshot, on the summed weekly path, is 160%. A 35% drawdown cap of the kind copy-trading badges use would shut out about 95% of these wallets. Our summed path is not the platforms' own drawdown measure, so this is an approximation.

## Secondary (no pass mark; read as leads, not findings)

| Split | Groups (wallet-snapshots) | Median t_after | Blew up afterwards (drawdown ≥ 35%) |
|---|---|---|---|
| Inside G2: t_before ≥ 2 vs below | 16 vs 109 | 1.07 vs 0.71 (difference +0.37, 95% interval −0.26 to +0.92) | **44% vs 85%** (difference −0.42, interval −0.71 to −0.04) |
| G2 pass vs fail | 125 vs 280 | 0.76 vs 0.70 (+0.06, −0.24 to +0.34) | **80% vs 65%** (+0.15, +0.03 to +0.26) |
| G1 pass vs fail | 19 vs 386 | 0.98 vs 0.72 (+0.26, −0.43 to +0.56) | 47% vs 71% (−0.24, −0.52 to +0.08) |
| All: t_before ≥ 2 vs below | 26 vs 379 | (see retrospective freeze) | 42% vs 72% |

- **The allocator-style gate (G2: 8 months, 52-week return above 20%, return over drawdown above 2.5) picked wallets that blew up more often afterwards, not less.**
- **Inside that gate, the wallets with t_before ≥ 2 blew up about half as often as the rest.** That rests on 16 wallet-snapshots from 11 wallets.
- Neither gate cleared bar(200) = 3.69 for any wallet that passed it.

## Why these are leads and not findings

- Eleven comparisons are reported here without a pass mark; two intervals exclude zero, and with that many looks one could do so by chance.
- Not blind: the author knew the pooled t_before split before writing the rule.
- The t ≥ 2 group inside G2 is 11 wallets.
- Returns are correlated within the same weeks, which wallet resampling ignores, so the intervals are likely too narrow.
- Both gates are approximations of the platforms' rules on Hyperliquid data, on a summed-return path, not the platforms' own scores.
- Only wallets with 8 weeks on both sides are scored (68% of cohort slots); who drops out is not random.

## What would turn a lead into a finding

The same split on the frozen 2026-10-14 cohort at its 2026-12-09 reading, written down now: inside G2 on the record before the freeze, the blow-up share after the freeze for t_before ≥ 2 against the rest. It will be reported at that reading next to test 3, with no pass mark: one forward cohort of 200 is too small to give this split one.
