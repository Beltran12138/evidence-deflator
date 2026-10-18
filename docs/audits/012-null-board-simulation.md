# Audit 012 · What luck alone puts at the top of a Hyperliquid-sized board (2026-10-18)

The subject is our own verdict "promising, not proven" (t ≥ 2) when it is read off a board ranked by profit. The method page has said since 2026-10-18 that this needs a simulation we had not published. This is that simulation.

## Question

On a board of 47,270 accounts where nobody has any skill, ranked the way Hyperliquid ranks (all-time PnL; 30-day ROI among accounts of $10k or more), how many of the top 100 reach t ≥ 2 by luck, and how often does anyone clear the bar for the best of 47,270 (4.90)? Then compare with the real board on the same day.

## Finding

**On the all-time PnL board, "promising" is what luck produces. On the 30-day ROI board, the real top 100 has more of it than luck explains.**

| Board (top 100) | Luck alone: share with t ≥ 2, median (5th–95th percentile) | Real board 2026-10-18 | Real board, t after BTC |
|---|---|---|---|
| All-time PnL | 15% (10–20%) | 9 of 98 (9%) | 9 of 98 |
| 30-day ROI, account ≥ $10k | 4.3% (1.1–8.0%) | 15 of 85 (18%) | 13 of 85 (15%); 11 without the two that never had a losing week |

- **PnL board.** Ranking by dollars favours large accounts that had a lucky run, and their t is inflated: with no skill anywhere, about 15 of the top 100 reach t = 2. The real board has 9, at the 4th percentile of what luck gives. Nothing on this board is more "promising" than chance; the wallet page's "promising" on a PnL-board wallet should be read that way.
- **30-day ROI board.** Ranking by last month's return picks recent streaks, but t is computed on the whole record, so luck gives few t ≥ 2 (about 4). The real board has 15, or 13 after taking out BTC's moves, above the 95th percentile of luck in every variant we ran. Something other than luck is in that group: skill, or strategies with a steady structural edge (market making, funding carry) that the board happens to surface.
- **Strong evidence.** In 200 simulated boards, nobody cleared 4.90 on either board (luck's best t: median 3.1 on the PnL board, 2.6 on the ROI board). The bar behaves as designed.

## How it was simulated

- Script: [`tools/null_board_sim.py`](https://github.com/Beltran12138/evidence-deflator/blob/main/tools/null_board_sim.py); output: [`null-sim.json`](/data/hl/null-sim.json) (200 boards, seed 7).
- Each simulated account has: a record length drawn from the lengths on the real top-100 boards (older than the average account, which helps luck); a size from a log-normal (median $30k); a weekly volatility from a log-normal (median 8%); weekly returns from a Student t with 3 degrees of freedom, mean zero. PnL is return times size. Each top-100 record is scored with the wallet check's estimator.
- The real board: [`latest.json`](/data/hl/latest.json), fetched 2026-10-18 09:20 UTC; the BTC-adjusted t is the wallet page's second number.

## Sensitivity

60 boards per variant. The PnL result moves with how unequal account sizes are; the ROI result does not move out of its conclusion.

| Variant | PnL board, luck median (95th) | Real at percentile | ROI board, luck median (95th) | Real at percentile |
|---|---|---|---|---|
| Base (t, 3 dof; size σ 1.8) | 15% (20%) | 4th | 4.3% (8.0%) | 100th |
| Thinner tails (5 dof) | 17% (23%) | 2nd | 5.8% (10.5%) | 100th |
| Fatter tails (2.5 dof) | 13% (18%) | 17th | 3.7% (6.5%) | 100th |
| Sizes more equal (σ 1.0) | 22% (27%) | 0 | 4.3% (8.7%) | 100th |
| Sizes less equal (σ 2.5) | 12% (16%) | 18th | 4.4% (7.5%) | 100th |
| Volatility median 4% or 16% | 15% (19%) | 10th | 4.3% (7.7%) | 100th |

Volatility level does not matter: t is scale-free, and scaling every account's volatility scales every PnL alike.

## What this does not show

- Accounts here are independent. Real accounts copy each other and trade the same moves, which makes groups of them rise together; that would raise luck's numbers on both boards, so the ROI result is an upper bound on how much is not luck.
- Mean zero with no market: the real board traded through BTC's moves. The BTC-adjusted column covers the linear part.
- The ROI board's excess is a group property. It does not say which of the 13 is skilled; each still sits below 4.90. That is what the frozen cohort (first reading 2026-12-09) is for.
