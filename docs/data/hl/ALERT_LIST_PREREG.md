# Pre-registration · Is there a list to alert on, and is t the right way to rank it? (2026-11-19)

Two questions from the 2026-11-19 council (grok's point): a debunking tool and a "who to follow" list cannot share one bar. Debunking naturally ends in "almost nobody clears it"; a follow list needs names. If the bar we use leaves the list nearly empty, there is nothing to alert on. And if a simpler signal (share of winning weeks, or the shrunk estimate) predicts the next weeks better than t, t should not be what ranks a list.

Written before anything below is computed. Results go under "Results" without changing anything above that heading.

## What we have already seen (stated so it is not mistaken for a blind result)

- The daily board on 2026-11-19 (`latest.json`, top 100 by all-time PnL and top 100 by 30-day ROI) shows **1** wallet with full-history t ≥ 4.90 and 24 with t ≥ 2. That is the top 200 only, not the population.
- The 1,500-wallet random sample behind `SHRINK_PREREG.md` reported 5.1% at z ≥ 2 on records cut at the freeze. Its count at t ≥ 4.90 has not been computed.
- No forward score for any cohort wallet, and no winning-week share for any wallet, has been computed.

## Part 1 · How many wallets could be alerted on (computed today)

- **Alertable** = full-record t (`hl_wallet.score`, weekly, the site's estimator) ≥ bar(N), N = accounts on the public leaderboard on the run day. Today N ≈ 48,000, bar ≈ 4.90: the bar the site applies to a wallet found anywhere on the board.
- **Data**: the 1,500 wallets drawn for the shrink test (`random.Random(20261110).sample`, portfolios cached 2026-11-10), scored on their **whole** cached record (not cut at the freeze). Wallets with fewer than 8 intervals are counted as not alertable and reported.
- **Estimate**: alertable share among the 1,500 × N. 95% interval: Clopper–Pearson on the count, scaled the same way.
- **Decision (grok's line of 15)**:
  - Upper end of the interval < 15 → **no list at this bar**: the copy-list route is dropped from the candidate pool.
  - Point estimate ≥ 15 → **a list exists**; Part 2 decides how to rank it.
  - Anything else (point < 15, upper ≥ 15) → **not enough sample**: draw 5,000 more wallets (`random.Random(20261119)`, from the same day's board, excluding the first 1,500), score them the same way, and apply the same rule to all 6,500 once. If still undecided, record "undecided" and stop; no third draw.

## Part 2 · Which pre-freeze signal predicts the forward record (read 2026-12-09)

On the frozen cohort (`cohort-2026-10-14.json`), at the same reading as `SHRINK_PREREG.md` and with the same forward fetch.

**Predictors, all from the record cut at the freeze** (`until(pf, frozen_at_ms)` in `tools/shrink_test.py`):
- `t`: `z_before` as recomputed in `shrink/estimates.json`.
- `shrunk`: the posterior mean in `shrink/estimates.json` (already committed 2026-11-11).
- `hit`: share of scored weekly intervals with return > 0.
- `pnl_rank`: all-time PnL at the freeze (higher is better), as in `retro/`.

**Outcomes**: `z_after` (forward t, the same as the ordering and shrink tests) as primary; the forward summed weekly return as secondary (Tessera's claim is about PnL persistence).

**Primary comparison**: Δ_hit = ρ(hit, z_after) − ρ(t, z_after) and Δ_shrunk = ρ(shrunk, z_after) − ρ(t, z_after), Spearman, wallets that have both a predictor and a forward score. 95% intervals by resampling wallets (10,000 draws, seed 20261209).

**Decision**:
- Either Δ's interval wholly above 0 → **t does not rank lists**. Any list ranks by the winner (the larger Δ if both).
- Either Δ's interval wholly below 0 for that signal → that signal is dropped as a ranking candidate.
- Both intervals contain 0 → **no ranking claim**: no list may be presented as "best first" on any of these signals until a later pre-registered reading says otherwise.
- Fewer than 30 wallets with every predictor and a forward score → "not enough data"; same move as the shrink test (2027-01-06, same rules).

**Reported with no pass mark**: the same Spearman for `pnl_rank`; all four against the forward summed return; the 2 × 2 of `hit` ≥ 0.6 vs `t` ≥ 2.

## Known limits

- **Power.** Around 150 wallets and eight forward weeks: a Δρ smaller than about 0.15 will not be detected. A null here is "not shown", not "no difference".
- **Correlation.** Wallets trade the same weeks; wallet resampling ignores the common shock, so intervals are likely too narrow (as in the shrink test).
- **Part 1 uses records to 2026-11-10**; the board N is from 2026-11-19. Both are reported.
- **Winning-week share is not trade win rate.** It is the closest quantity our data supports (portfolio history, not fills).

## Not done

No change of bar, sample, seed, predictor definition, outcome or rule after this file is committed.

## Results
