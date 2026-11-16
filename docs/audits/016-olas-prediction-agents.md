# Audit 016 · Olas prediction agents: beating the price, and paying for the prediction (2026-11-16)

The subject is the performance Olas shows for its prediction-market agents. No single agent is the subject.

## Subject

Olas runs autonomous trader agents that bet on prediction markets: Omen on Gnosis and Polymarket on Polygon. Every bet is on chain and indexed in Olas's own public subgraphs. The set of agents is known, so the number of candidates behind any "best agent" can be counted.

Olas's site shows three figures for the fleet: ROI, "Prediction accuracy" and a Brier score. This audit asks the question those figures leave out: did the agents get back more than they paid?

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (live betting) |
| Window | Omen 2023-07-12 to 2026-11-16 (23,063 markets); Polymarket 2026-01-21 to 2026-11-16 (4,455 markets); resolved markets only |
| Attempts | 2,330 agents with at least one resolved market: 2,141 on Omen and 189 on Polymarket. The bar for the best of them is t = 4.27 |

## What Olas's figures measure

These points come from Olas's published code. No data is needed for them.

- **Brier score.** The probability scored is the price the agent paid. Olas's indexing doc describes it as the "Implied probability the market assigned to `outcomeIndex` at trade time". An agent with no view at all, buying at fair prices, gets the market's Brier.
- **Prediction accuracy.** It is the share of settled bets that won. Buying outcomes priced at 0.9 wins about nine times in ten with no skill.
- **Neither figure** compares what came back with what went out.

## Finding

The test was pre-registered and pushed before any bet was fetched (`docs/data/olas/PREDICT_AGENTS_PREREG.md`).

**On Omen, 365 agents beat the prices they paid by more than luck allows, given 2,330 candidates. On Polymarket, none did.** The prediction tools the agents pay for were left out of that test. Counting them, the Omen fleet lost 19% of what it bet, and 3 agents still clear the bar.

| | Omen | Polymarket |
|---|---|---|
| Agents with ≥ 20 resolved markets | 1,609 | 110 |
| Clear t = 4.27, bets only (pre-registered) | **365** | **0** (highest t 1.19) |
| Fleet mean return per market, bets only, 95% interval | +9.0% [+8.4, +9.6] | −8.3% [−10.1, −6.5] |
| Clear t = 4.27 after tool costs (post-hoc) | **3** | not computed |
| Fleet return on money bet, after tool costs (post-hoc) | **−19.2%** | not computed |

- **Bets only.** The top agents each played about 3,200 markets and made 26% to 29% per market against the price they paid, with t near 19. On Omen the agents' picks are better than the market maker's prices, and the edge is far beyond luck.
- **Tool costs.** Before most bets an agent pays a "mech" for a prediction. Olas's own ROI charges 0.01 xDAI per request. Charged the same way, the agents' requests cost 92,226 xDAI against 9,418 xDAI won on 430,905 bet in resolved markets. The predictions cost almost ten times what they won. The median agent goes from +2.7% to −49%.
- **One example.** The agent with the highest t (`0x3895…dbb4ab`) bet 112.57 xDAI over 3,189 markets and got 136.39 back, a gain of 23.82. It made 14,783 mech requests, which come to 147.83 xDAI.
- **Polymarket.** The agents there trail the prices they paid even before tool costs. Their returns move together (median pairwise correlation 0.72), so the 110 agents behave close to one strategy.

## How it was computed, and what is uncertain

**Data.**
- Olas subgraphs `predict-omen` (graph-node) and `predict-polymarket` (SQD squid), fetched 2026-11-16 with no key: 2,401,894 Omen bets and 24,234 Polymarket bets.
- Mech requests come from Olas's marketplace subgraph on Gnosis.
- Scripts:
  - `tools/olas_fetch.py`
  - `tools/olas_predict_test.py`
  - `tools/olas_mech_costs.py`
  - `tools/olas_posthoc_mech.py`
- Results are in `docs/data/olas/2026-11-16/`. The raw responses (about 1 GB) are kept outside the repository.

**Unit.** One agent in one resolved market. cost = buys paid − sells received. payout = tokens held × what each outcome paid. R = (payout − cost) / buys paid.

**Bar.** t of an agent's mean R over its markets, against the best-of-N bar for N = 2,330, the same bar used across Evidence Deflator. With no edge and fair prices R is slightly negative (fees), so testing against zero leans against finding skill.

**Measurement check.** For the agent with the highest t, the payout computed here equals Olas's own `expectedPayout` in all 3,189 of its markets.

**Tool costs are post-hoc and the least certain part.**
- They were not in the pre-registered test, which listed them under "does not test". They were added after the result came in, so the "−19%" and "3 agents" figures are a second look, not the test.
- Each agent's lifetime requests are charged at Olas's 0.01 xDAI. The charge is spread over its resolved markets in proportion to its bets in them, and it includes requests that led to no bet.
- Olas's code comments describe healthy mech costs as 2% to 6% of settled trading costs. The charge here comes to 21%. The gap is not explained, so the size of the loss is uncertain.
- Its sign is not: the bets earned 2.2% of what they risked, so any tool cost above 2.2% of the amount bet turns the fleet negative.

**Staking rewards are not counted.** Olas agents also earn OLAS for staying active, and Olas's "final ROI" adds them. This audit scores the betting only.

**Who is on the other side.** On Omen, the agents trade against automated market makers. Every market in the data was opened by one of two creator agents tracked in Olas's subgraph (16,935 and 6,380 markets). Beating those prices says the agents' picks beat the opening odds. It does not show they would beat a deep market. Polymarket, the deeper venue, is where they did not.

**Counts.** Olas's site says 1,215 Omen agents were "ever registered". The Omen subgraph holds 3,659 trader agents, of which 2,141 have a resolved market. The audit uses the subgraph.

## What it would take

Olas could show, per agent and for the fleet, what came back against what went out with the mech requests included. Its own ROI already does this, but its "accuracy" and Brier tiles sit next to it and measure the price, not the agent.

The median Omen bet is 0.025 xDAI (the mean is 0.18). An agent buying predictions at 0.01 xDAI each to place bets that size pays a large share of each bet for its information before it can win anything. Bet size, not forecasting, decides whether these agents make money.

Recheck: when Olas publishes a change to its mech pricing or its default bet size.
