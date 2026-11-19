# Evidence audits

One page each. Every audit answers a single question: **how much of the evidence behind an AI trading claim actually counts?**

The method needs three things: the model's knowledge cutoff, the test window, and how many attempts the result was picked from. Where a project does not publish them, the audit says so; a missing input is a finding, not a verdict on the project.

Rules every audit follows:

- Sources are public and fetched on the stated date. Numbers are recomputed, not copied.
- "Cannot be ruled out as seen" is the strongest claim made about a model's training data. Never "contaminated".
- Findings state what is missing or what the numbers can and cannot support. No judgement of intent.
- Short is not the same as wrong: an underpowered result has not been shown to fail, only not shown to work.
- A verdict holds at the level of the record it was computed on, and says nothing about the levels above it.

**Record** is what the audit actually read, not where the trades happened:

| Level | What was read | What a verdict at this level cannot tell you |
|---|---|---|
| L0 | A claim, with no record published | Anything about performance |
| L1 | A backtest: the strategy was chosen, or the model may have learned, on the test window | Whether it works on data it has not seen |
| L2 | Live trading with simulated money | What fills, fees, slippage and size would have cost |
| L3 | Real money, figures from the platform's or a board's own database, which nobody else can recompute | Whether the series is complete and unedited (closed accounts, missing losers, restated history) |
| L4 | Real money, read from the state of a public chain (its own endpoint, or an index of its trades) that anyone can recompute | Whether the edge will last: a complete past record is still not a forecast, and the statistical bar still applies |

Freezing a board before a forward reading (009, 010) and pre-registering a test (016) are separate from the level: they fix what is tested before the outcome is known, at whatever level the record sits. 012 tests our own verdict on simulated boards and has no level.

| # | Subject | Record | Date | Finding |
|---|---|---|---|---|
| [001](001-catalyst.md) | Catalyst (AI trading agents for retail) | L0 | 2026-10-12 | Cannot assess: none of the three inputs is public. The only published number is trading volume, not performance. |
| [002](002-metisai.md) | MetisAI's Liquidity Arena result | L2 | 2026-10-12 | Literally true, but the comparison set was narrowed: Sharpe 4th of 41, drawdown 2nd worst, t ≈ 1.2 against a bar of 3.26. |
| [003](003-liquidity-arena-phase-1.md) | Liquidity Arena 2026 Track A, Phase I (41 teams) | L2 | 2026-10-12 | No team reaches t = 2; the highest is 1.63. The format is closed-book; the window is too short. |
| [004](004-tradingagents-backtest.md) | TradingAgents `run_backtest` | L1 | 2026-10-12 | Data-level look-ahead is handled carefully; weight-level look-ahead is not checked. A 2024–2026 run with the default model is 88% open-book. |
| [005](005-nof1.md) | Nof1's "proto scaling law for financial intelligence" | L0 | 2026-10-12 | Cannot assess: the claim is public, the evidence is not. |
| [006](006-alpha-arena-season-1.md) | Alpha Arena Season 1 (6 LLMs, real money on Hyperliquid) | L3 | 2026-10-15 | No model is distinguishable from luck in either direction: the winner's t is 0.54, the worst loser's −0.83. 17 days needs a Sharpe of about 9.3 to reach t = 2. |
| [007](007-cex-copy-trading.md) | Copy-trading boards on OKX and Binance (profit top 100 each) | L3 | 2026-10-15 | 0 lead traders clear the bar for being picked from the board (OKX 0/97, Binance 0/83); about one in ten passes a single test. |
| [008](008-polymarket-profit-board.md) | Polymarket all-time profit board (top 50), position by position | L4 | 2026-10-15 | 0 of 38 complete records clear the bar. Reading only closed positions made 11 look like stars: unredeemed losers sit in a different list. |
| [009](009-kolscan-kol-board.md) | kolscan's Solana KOL profit board (1/7/30 days) | L3 | 2026-10-15 | Cannot assess: the longest window is 30 days and there is no capital base. 33 of the 30-day top 47 lose more trades than they win. Board frozen; recheck 2026-11-14. |
| [010](010-papertrade-leaderboard.md) | Papertrade's PnL leaderboard (Paperdash, all-time and 24h) | L3 | 2026-10-16 | Cannot assess yet: no return series. #1 by PnL is the wallet The Block tied to price manipulation; one of the biggest winners ranks third from last. Three groups frozen; readings 2026-10-23 and 2026-10-30. |
| [011](011-recall-perps-competitions.md) | Recall's perps competitions for AI agents (10 competitions, live on Hyperliquid) | L3 | 2026-10-17 | 0 of 149 scored entries clear the bar for their field; 1 reaches t = 2. Four to six days would need a Sharpe of 22 to 30. Whether winners repeat cannot yet be told from chance. |
| [012](012-null-board-simulation.md) | Our own "promising" verdict on Hyperliquid-sized boards, against 200 simulated boards with no skill | — | 2026-10-18 | On the PnL board, luck alone gives 15% of the top 100 at t ≥ 2 and the real board has 9%: "promising" there is chance. On the 30-day ROI board luck gives 4% and the real board 18% (15% after BTC), above luck in every variant. Nobody clears 4.90 in 200 simulated boards. |
| [013](013-traderank-arena-and-jev.md) | TradeRank's LLM trading arena (10 seasons plus the running one) and Jev, TypeSafe's decision model | L2 · L1 (Jev) | 2026-10-20 | No model in any scored season reaches t = 2; the running season's leader is at 1.19 against a bar of 3.08. Since Season 7 models average 3 to 7 trades a season. TradeRank's own Jev backtest: +17.52% and −17.35% on two runs of the same window. No Jev trading bot we found publishes a mainnet wallet. |
| [014](014-cicc-loop-factor-engine.md) | CICC's LLM agent loop that searched China A-share price-volume factors (report of 2026-08-03) | L1 | 2026-10-20 | 16,939 candidates backtested, 69 kept; every figure is on the window the filters were scored on (2025-01-01 to 2026-07-08). Best single factor t = 3.37, top-five blend 3.86, against a bar of 4.69 for the search. The loop logs its trial count but reports nothing adjusted for it. |
| [015](015-vault-depositor-gap.md) | What Hyperliquid vault depositors kept of the vault curve (60 largest open vaults, 27 usable) | L4 | 2026-11-03 | In the 20 vaults with a positive curve, listed depositors kept a median 85% of it after the leader's share; 12 of 20 kept less. In the 9 best curves the median was 78%. A lower bound: depositors who left are not listed. |
| [016](016-olas-prediction-agents.md) | Olas prediction-market agents on Omen and Polymarket (2,330 agents with a resolved market) | L4 | 2026-11-16 | Pre-registered: on Omen 365 agents beat the prices they paid beyond luck for N = 2,330; on Polymarket none. Post-hoc, with the mech (tool) costs Olas itself charges: the Omen fleet lost 19% of what it bet and 3 agents clear the bar. |
| [017](017-liquidwhales-grades.md) | LiquidWhales S–F grades for Hyperliquid wallets (28,623 graded) | L4 | 2026-11-19 | Pre-registered: none of the 3 S wallets clears the bar for N = 28,623 (t 1.10, 1.44, 2.41); 2 of 88 scorable S/A wallets do, inside the no-claim band. 29 of the 134 listed wallets are sub-accounts; one master holds five graded places. |

Computed with [Evidence Deflator](../../README.md). Have a backtest or a claim you want checked? Open an issue with a link to it.
