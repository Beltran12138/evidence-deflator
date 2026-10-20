# Pre-registration · Does the ruler order wallets? (2026-10-20)

Applies to the frozen cohort `cohort-2026-10-14.json` (200 wallets, frozen 2026-10-14 09:48 UTC). Reading on 2026-12-09, together with test 2 on the record page.

## Why this is added

Test 2 asks whether these boards pick up forward skill. It does not ask whether our own score can tell better wallets from worse ones, which is what any use of the score as a gate depends on. Test 2 already reports, with no pass mark, the share of wallets with t > 0 after the freeze for those with `t_before` ≥ 2 against the rest. This file adds a pass mark for ordering.

## Timing and what we have seen

Written 2026-10-20, six days after the freeze. No wallet has eight weeks of post-freeze record, and no post-freeze-only score has been computed by our tools. The daily Hyperliquid board does show full-history t for wallets still on it, which includes the post-freeze weeks; we have not used it for this test.

## Data

- `t_before`: as stored in the frozen file (record up to the freeze).
- `pnl_before`: `pnl_all_time_before` in the frozen file.
- `t_after`: `weekly_returns(pf, since=frozen_at_ms)` + `score()`, at least 8 weekly intervals, fetched on the reading day. Same estimator as the wallet check.
- Wallets without a usable `t_before` or without 8 weeks after the freeze are left out; the count left out is reported.

## Primary test: ordering

ρ_t = Spearman(`t_before`, `t_after`), with a 95% bootstrap interval resampling wallets (10,000 draws, seed 20261209).

- **The ruler orders**: the interval excludes 0 and ρ_t > 0.
- **The ruler does not order**: ρ_t ≤ 0. We then stop describing the score as usable for gating money, and say so on this page.
- Anything else is **inconclusive**, reported as such.

## Secondary test: better than ranking by profit

ρ_pnl = Spearman(`pnl_before`, `t_after`). Report ρ_t − ρ_pnl with a wallet-resampled 95% interval. We claim "better than profit rank" only if that interval excludes 0. (The retrospective test of 2026-10-15 did not clear this.)

## Reported with no pass mark

- Median `t_after` for `t_before` ≥ 2 against the rest.
- ρ_t separately for the PnL board and the ROI board.

## Too little data

Fewer than 30 wallets with both scores is "not enough data"; the reading moves to 2027-01-06 under the same rules.

## Not done

No change of estimator, cutoff, minimum weeks, or subset after this file is committed. Wallets' weekly returns are correlated within the same weeks, which wallet resampling does not handle, so the interval is likely too narrow; this is stated with the result, not used to move the line.
