# Pre-registration · Olas prediction agents: does any of them beat the price it paid? (2026-11-16)

Olas runs autonomous trader agents that bet on prediction markets: Omen on Gnosis ("Omenstrat") and Polymarket on Polygon ("Polystrat"). Every bet is on chain and indexed by Olas's own public subgraphs, and the set of agents is known, so the number of candidates (N) behind any "best agent" is observable. Olas's website shows three performance figures for the fleet: ROI, "Prediction accuracy" and a Brier score. This file fixes, before any bet is fetched or scored, what will be computed and what each result will be taken to mean. Run on or before 2026-11-18; results go under "Results" without changing anything above that heading.

## What was looked at before writing this

- Olas's public pages (olas.network/agent-economies/predict, fetched 2026-11-16): "1,215 Omenstrat agents ever registered on Gnosis", "141 Polystrat agents ever registered on Polygon", "75% prediction accuracy … over the last 30 days", "-4% average trading return … since 22 November 2025".
- The Polymarket squid's agent count (`traderAgentsConnection.totalCount` = 232) and the three Omen agents with the most bets: their `totalBets`, `totalTraded` and `totalPayout` (payout over traded about 1.05, 1.05 and 0.99; these totals mix settled and unsettled markets and ignore fees).
- Both schemas (GraphQL introspection) and the indexing code and docs in `valory-xyz/autonolas-subgraph` (commit 593dbdb, 2026-11-12) and the metric code in `valory-xyz/olas-website` (commit 3227092, 2026-11-12).

No bet, market resolution or per-agent return has been fetched or computed beyond the totals above.

## What the code says Olas's figures measure (no data needed)

- **Brier score.** `BRIER_SCORE.md`: the probability scored is `Bet.impliedProbability`, "Implied probability the market assigned to `outcomeIndex` at trade time" (buy price = amount / tokens). The Brier shown for the agents is therefore the Brier of the prices they paid, not of any forecast the agent made. An agent with no view, buying at fair prices, gets the market's Brier.
- **Prediction accuracy.** `olas-website/common-util/api/predict/accuracy.ts`: `accuracy% = won / total * 100` over settled bets, pooled across agents. A win rate rises with the price paid: buying outcomes priced at 0.9 wins about 90% of the time with no skill at all.
- Neither figure compares what was won with what was paid. That comparison is what this test makes.

## Data

- **Sources** (no key): Omen `https://api.subgraph.autonolas.tech/api/proxy/predict-omen`; Polymarket `https://subgraph.autonolas.tech/squid/predict-polymarket/graphql`. Fetched once, at time T0 on the run day; raw responses saved under `docs/data/olas/<T0 date>/`.
- **Agents**: every `TraderAgent` in each source.
- **Bets**: every `Bet` of those agents: market, outcome index, amount, fee, outcome tokens (shares), timestamp. Omen: `amount` positive for a buy, negative for a sell; cost of a buy = amount (gross; `feeAmount` is recorded but is part of the amount paid into the market maker and is not subtracted again). Polymarket: `amount` includes the exchange fee; sells are non-positive.
- **Resolution**: Omen `fixedProductMarketMaker.currentAnswer` (index of the winning outcome; `0xff…ff` = invalid, each token pays 1/2). Polymarket `Question.resolution`: `winningIndex`, or the `payouts` vector when `winningIndex` is −1. Markets without a resolution at T0 are left out. A market re-answered after T0 is taken as answered at T0.

## Unit of analysis: one agent in one market

For agent a in resolved market m: cost = sum of buy amounts − sum of sell proceeds; tokens held per outcome = sum of tokens bought − tokens sold; payout = tokens of the winning outcome (or the payout vector applied to holdings); **return R(a,m) = (payout − cost) / (sum of buy amounts)**. A bet-by-bet unit is not used, because several bets in one market are one position.

With no skill and fairly priced markets, the expected R is slightly below zero (fees). Testing against zero therefore leans against finding skill.

## Primary test · per agent

- **Eligible**: agents with at least 20 resolved markets with a buy.
- **Statistic**: t = mean R / (sd R / √M) over the agent's M eligible markets.
- **N for the bar**: every agent with at least one resolved market, both venues together (all of them were run; any could have been the one shown). Bar = the best-of-N bar used across Evidence Deflator: 2 for one record, Bonferroni at one-sided 2.275% for N (`forecast_score.bar(N)`).
- **Read**: the number of eligible agents with t ≥ bar(N) is "agents that beat the price they paid by more than luck allows given N". Also reported: how many have t ≥ 2, against the 2.275% × (eligible count) expected by luck alone.

## Secondary tests

1. **Fleet edge**, per venue: mean R over all agent-markets, 95% interval from a bootstrap over agents (2,000 draws, seed 20261116). Interval entirely below 0 → "the fleet as a whole paid more than it got back"; entirely above 0 → it beat market prices; otherwise no conclusion.
2. **What "accuracy" tracks**, eligible agents, per venue with at least 30 eligible: Spearman ρ between an agent's win rate (share of its eligible markets with payout > cost) and (i) its mean buy price, (ii) its mean R. My stated expectation: ρ(win rate, price) ≥ 0.5 and greater than ρ(win rate, R). If ρ(win rate, price) < 0.3 I drop the claim that the displayed accuracy mostly reflects the prices paid.

## Descriptive only (no verdict)

- Effective N: many agents run the same code and bet on the same markets, so they are not independent; the bar above is computed with the raw count and is therefore strict. Reported: median pairwise correlation of R across agents that share at least 10 markets.
- The top 5 eligible agents by t, with M, mean R and t.

## What this does not test

- **Staking rewards.** Olas agents also earn OLAS for staying active; the website's "final ROI" adds them. This test scores the bets only: whether the agents' choices beat the prices they paid.
- **Tool costs.** Agents pay for "mech" calls that inform their bets; these costs are left out, which favours the agents.
- **Unresolved and NegRisk/combinatorial Polymarket positions**, which the squid does not record.
- Whether agents registered before they first bet (the subgraphs have `firstParticipation` but not registration time); the record is on chain either way.

## Results

(Empty until the run.)
