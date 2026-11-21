# Audit 019 · x402's issue tracker: many sellers, no buyer in sight (2026-11-21)

The subject is what the public issue trackers of five agent-payment projects show about who is building and who is paying. No single person or project is the subject.

## Subject

x402 lets an AI agent pay for an HTTP resource in stablecoins. Its headline numbers are large. One tracker counted over 200 million transactions by June 2026. Visa and Artemis say the volume left after removing wash trading and self-dealing is about $15–19 million, cumulative ([Forkast](https://forkast.news/the-x402-foundation-activated-a-27-year-old-internet-code-200-million-transactions-later-the-real-volume-is-still-tiny/), [CURB](https://curb.numetal.xyz/dispatch/x402-economy-july-2026)). Those figures are second-hand and not rechecked here.

This audit looks at a different record of the same market: the issues people open on the projects' GitHub repositories. If agents were spending real money at scale, some of the people affected would show up there with money that went missing, was charged twice, or bought the wrong thing. The question is how many do, compared with everyone else who opens issues.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (no model is being scored) |
| Window | Every issue (pull requests excluded) from each repository's start to 2026-11-21 |
| Attempts | Not a best-of-N test. This audit was **not pre-registered**: the issues had been read before the method was fixed, so every figure below is a description, not a test |

Repositories: `x402-foundation/x402` (970 issues), `google-agentic-commerce/AP2` (110), `agentic-commerce-protocol/agentic-commerce-protocol` (109), `stripe/ai` (85), `coinbase/agentkit` (206). Total 1,480.

## Finding

**A search of all 1,480 issues found no report of a buyer losing money in production, and a hand-read random 80 of x402's 970 found none either. About half of those 80 come from the sell side: protocol proposals and listing requests for the poster's own service.** (The search can miss reports worded in ways it did not anticipate.) The busiest threads are vendors discussing their own receipt and dispute products with each other; no maintainer has commented in any of them.

**1. A random sample of x402 issues, labelled by hand.** 80 issues drawn with a fixed seed (20261121) from the 970, each read and given one label:

| Label | What it means | Count |
|---|---|---|
| Proposal | New scheme, extension, spec change or feature, usually with the poster's own implementation | 29 (36%) |
| Listing or showcase | "Add my service or facilitator to the ecosystem", or a showcase of the poster's product | 12 (15%) |
| Bug | Something in the SDKs, spec or hosted services does not work as documented | 24 (30%) |
| Question | Usage or docs question | 4 (5%) |
| Other | Bot reports, dependency bumps, withdrawn or off-topic posts | 11 (14%) |
| **Money lost or wrongly charged in production** | | **0** |

With 0 of 80, the share of such reports among x402's issues is below about 3.8% at 95% confidence (rule of three), that is, at most about 36 of 970.

The share from the sell side (proposals plus listings) does not trend clearly in the sample: 6 of 13 issues from 2025, 17 of 26 from the first half of 2026, 18 of 41 from the second half.

**2. A search of all 1,480 issues for money that moved wrongly.** Titles and bodies were searched for first-person reports of loss or overcharge ("we paid", "charged twice", "funds lost", "overcharged", "never received" and similar). Four issues matched. Two were false matches. The other two are real defects, both found by testers on Base Sepolia, a test network:

- [#1805](https://github.com/x402-foundation/x402/issues/1805): five concurrent paid requests to a public test endpoint produced five debits from the buyer's wallet, and the merchant later refunded four.
- [#3866](https://github.com/x402-foundation/x402/issues/3866): a server that asks for ten times the price is paid ten times the price by the official client. The only guard is the caller's own per-payment limit.

Neither reports a user who lost money on mainnet.

**3. The busiest threads.**

| Issue | Comments | Distinct commenters | Most by one account | Comments from owners, members or collaborators |
|---|---|---|---|---|
| [#2332](https://github.com/x402-foundation/x402/issues/2332) post-settlement accountability layer | 238 | 19 | 63 | 0 |
| [#2887](https://github.com/x402-foundation/x402/issues/2887) correctness/dispute layer | 233 | 25 | 32 | 0 |
| [#2833](https://github.com/x402-foundation/x402/issues/2833) delivery-receipt attestation | 138 | 20 | 21 | 0 |
| [#1777](https://github.com/x402-foundation/x402/issues/1777) agent-trust extension | 124 | 20 | 27 | 0 |
| [#1195](https://github.com/x402-foundation/x402/issues/1195) settlement attestation receipt | 120 | 14 | 54 | 0 |

Read in sequence, these threads are vendors describing their own receipt, attestation and dispute products, running each other's test vectors and asking for badges.

**4. Who the maintainers answer.** Four accounts appear as owner, member or collaborator in x402's comments. They commented on 262 of the 970 issues (27%). In the hand-labelled sample:

| Label | Issues with a comment from those accounts |
|---|---|
| Listing or showcase | **11 of 12** |
| Bug | 5 of 24 |
| Proposal | 2 of 29 |
| Question | 0 of 4 |
| Other | 1 of 11 |

The maintainers do answer. What they answer most is requests to be listed in the ecosystem. The receipt and dispute proposals that fill the busiest threads get almost no reply. A bug can also be fixed through a pull request without a comment on the issue, so the bug row understates attention to bugs.

## How it was computed, and what is uncertain

**Data.** GitHub REST API via `gh`, fetched 2026-11-21. Issue titles, the first 600 characters of each body, comment counts and reactions, plus the author and GitHub's `author_association` for every comment on x402 issues that have comments. Files, scripts and the 80 hand labels are in `docs/data/agentpay/2026-11-21/`; `python numbers.py` there recomputes every figure in this audit and checks that the sample reproduces from its seed.

**Labels.** One person, the author of this audit, labelled the 80 issues, with no second labeller. The labels are published issue by issue so anyone can relabel them. A keyword classifier tried first agreed poorly with the hand labels (precision 0.68, recall 0.72 for "proposal"), so no figure here rests on keywords except the search in point 2, whose four matches were all read.

**"Maintainer".** GitHub marks a commenter as owner, member or collaborator only if their organisation membership is public or they have repository access. A maintainer with private membership shows up as a contributor. The zeros in point 3 are zeros for those three labels.

**What the tracker cannot show.** People who lose money do not usually file GitHub issues. They write to support, to the facilitator, to their bank, or on social media. A quiet tracker does not prove that nobody is losing money. What it shows is narrower: on the channel where builders meet, the visible traffic is people selling to the ecosystem, not people asking it to fix a loss.

**Not a test.** The issues were read before this method was written down. Nothing here was pre-registered, and the categories were chosen after looking. The figures describe one sample; they do not estimate a trend.

## What it would take

A protocol with real paying users would show it in the tracker: bug reports from mainnet, with transaction hashes and amounts. If x402's issues start to carry those, the gap described here is closing.

Recheck: in three months, with a new random 80 under the same labels, and when Artemis or Visa publish an adjusted volume for a later period.
