# Audit 013 · TradeRank's LLM trading arena, and Jev in it (2026-10-20)

The subject is the arena's format and the claims around Jev, not any one model's makers.

## Subject

[TradeRank](https://www.traderank.ai) runs month-long seasons in which AI models each trade $10,000 of simulated capital in the same 60 assets (10 cryptocurrencies, 50 US large caps), with one decision a day at 16:00 UTC. Ten seasons have ended since 2025-12-22; Season 10 (22 models) opened 2026-10-10.

[Jev](https://typesafe.ai) is TypeSafe's "decision model": it does not write text, it returns a probability for each answer to a typed question. It launched in September 2026 and was quickly wired into trading bots; TradeRank added it to Season 9 on 2026-09-18 as the one entrant that is not a language model. Media coverage presents it as a fast, cheap brain for trading agents.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Live seasons: not applicable, closed-book by construction. TradeRank's Jev backtest (2026-02-02 to 2026-06-23): Jev's training cutoff is not published, so that window cannot be ruled out as seen; TradeRank masks tickers, dates and raw prices, which reduces the risk. |
| Window | 20 to 34 days per season; the running season is at day 9 of 28. |
| Attempts | 4 to 22 models per season; the season winner is the best of that many. |

## Finding

**No model in any scored season clears the bar for its field, and none reaches even t = 2.** A 28-day season would need an annualised Sharpe of about 10 to 11 for its winner to clear. For Jev, TradeRank's own backtest already reports that its profit is noise: two runs of the same model over the same 142 days returned **+17.52% and −17.35%**.

- Data: TradeRank's public files and API, no key, fetched 2026-10-20 02:32 UTC: the season index (`/data/competitions/index.json`), the daily reports where published, and the running season's equity at every cycle close (`api.traderank.ai/api/arena/equities`). Script: `tools/audit_traderank.py`; output: [`traderank-2026-10-20.json`](/data/traderank/traderank-2026-10-20.json).
- Method: returns between cycle closes → the estimator behind the [wallet check](/wallet/) (Sharpe × √years, Student-t on effective degrees of freedom, back on the normal scale). The bar for the best of N is Bonferroni, one-sided.

### The running season (Season 10, day 9)

The bar for the best of 22 is **t ≥ 3.08**. Scored: 21 (one model's equity has not moved). t ≥ 2: **0 of 21**. The leader's t is 1.19.

| Model | Return | t |
|---|---|---|
| GPT-6.1 Sol Pro | +1.22% | 1.19 |
| Muse Spark 1.3 | +0.37% | 0.30 |
| Claude Opus 5.5 | +0.23% | 0.36 |
| Jev | −0.40% | −0.21 |
| Seed 2.1 Turbo | −7.82% | −1.41 |
| Mistral Large 4 | −8.08% | −1.87 |

Over the same days Bitcoin fell 1.21% and the S&P 500 1.43% (TradeRank's own figures), so a model that held cash beat most of the field.

### Ten finished seasons

| Season | Start | Days | Models | Winner | Winner's return | Winner's trades | Trades per model | Sharpe the winner would need |
|---|---|---|---|---|---|---|---|---|
| 0 | 2025-12-22 | 20 | 4 | Grok 4-1 Fast | +3.78% | n/a | 80.5 | 10.8 |
| 1 | 2026-01-11 | 28 | 9 | Reverse Kimi | +10.34% | n/a | 88.7 | 10.1 |
| 2 | 2026-02-08 | 28 | 13 | Reverse DeepSeek | +1.88% | n/a | 73.8 | 10.5 |
| 3 | 2026-03-23 | 34 | 9 | MiniMax M2.5 | −0.63% | n/a | 21.8 | 9.2 |
| 4 | 2026-04-26 | 27 | 9 | MiniMax M2.7 | +6.94% | n/a | 13.9 | 10.3 |
| 5 | 2026-05-23 | 28 | 10 | Gemini 3.5 Flash | +13.76% | n/a | 12.7 | 10.2 |
| 6 | 2026-06-20 | 28 | 11 | Kimi K2.7 Code | +2.14% | 13 | 14.5 | 10.4 |
| 7 | 2026-07-18 | 26 | 12 | Nemotron 3 Ultra | +1.98% | 2 | 3.2 | 10.9 |
| 8 | 2026-08-15 | 28 | 14 | Inkling | +12.82% | 7 | 7.3 | 10.6 |
| 9 | 2026-09-12 | 28 | 18 | Nemotron 3.5 Lightning | +3.84% | 4 | 5.3 | 10.9 |

Daily reports are published for only some seasons. The two with at least 20 (Seasons 1 and 6) were scored from the reports' cumulative returns: 0 of 8 and 0 of 11 reach t = 2; the highest t is 0.42 and 0.40. In Season 1 the published winner appears in only 5 of 23 reports, too few to score.

Since Season 7, models average **3 to 7 trades a season**, and two recent winners made 2 and 4. A result built on four trades cannot be told from luck by any statistic; the season's ranking orders the field, it does not measure skill.

## Jev

| What is claimed | Source | What the numbers show |
|---|---|---|
| "Zero Hallucinations"; "$42 Per Billion input tokens" | typesafe.ai | The price checks out: OpenRouter lists $0.042 per million input tokens, $0 per million output. "Zero hallucinations" is a claim about the output format (typed answers with a confidence figure), not about whether the answers are right. |
| "Most queries complete in about 100 ms" | docs.typesafe.ai | Consistent with secondary reports of 70 to 500 ms. Speed is not evidence of an edge. |
| Returns "calibrated probabilities" | jevymarket README (a third-party bot) | TradeRank's backtest: Jev's 80% price range held the outcome **68%** of the time, and its direction calls did no better than a formula that assumes each asset keeps its average drift (p = 0.66). |
| Backtest profit | TradeRank, "What Is Jev?", 2026-09-18 | +17.52% and −17.35% on two runs of the same model over the same window; −2.58% under the live sizing. Five identical requests returned probabilities up to 0.07 apart, so TradeRank asks each question five times and averages. |
| Season 9 result | TradeRank's Jev page | The same page gives two results: "16th of 18 … at −0.39%" in its summary and "8th of 18, −1.26%, 3 trades" in its results table. Either way, three trades. |
| Season 10 so far | TradeRank API | 1 closed trade (a loss) and two open short positions. At the day-9 close, 5th of 22 at −0.40%; at fetch time, marked to market, 3rd at +0.56%. The rank moves with two open positions. |

**Bots built on Jev publish no record that can be checked.** We looked at the two open-source Jev trading bots that coverage pointed to as live, and at the trading category of the Made with Jev directory. Neither bot publishes a mainnet wallet. jev-trade's README says "real fills"; its own `llms.txt` says the public desk "is a live testnet demo". jevymarket logs its trades to a local SQLite file "so Jev's calibration can be checked against resolutions later"; no results are published. The directory listed no trader wallet. That is a coverage of three places, not of every Jev bot.

## Why the window decides it

t = Sharpe × √years. A 28-day season is 7.7% of a year, so √years is about 0.28. Clearing a field of 9 to 22 needs a t of 2.80 to 3.08, so a winner would need an annualised Sharpe of about 10 to 11. The arena is a useful comparison of how models behave under the same rules; one season cannot rank them by skill.

## Limits

- Simulated capital at live prices: no slippage or market impact beyond what TradeRank models.
- Season 10's figures are at day 9 of 28 and will change. The finished seasons' trade counts and winners come from TradeRank's season index; the per-model scores for Seasons 1 and 6 come from daily reports, which are mid-season snapshots with gaps, not final standings.
- Daily returns of a portfolio that holds the same positions for days are not independent; positive autocorrelation would make the t values above too high, so the finding (no one reaches 2) is conservative in that direction.
- The Jev backtest numbers are TradeRank's, quoted, not recomputed; the backtest's data is not public.

## What would fix it

Publish each model's equity for every finished season (the running season's API already does), and the bar for the field size next to the standings. Keep the same models across seasons: a model that places well season after season builds a forward record, which no single season can. For Jev bots: a public wallet address is enough for anyone to run the [wallet check](/wallet/).

Recheck: when Season 10 closes on 2026-11-07 (`python tools/audit_traderank.py OUT.json`).
