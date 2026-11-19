# Audit 018 · LLM factor-mining agents: RD-Agent(Q) and QuantaAlpha against the luck bar (2026-11-19)

The subjects are two published claims about LLM agents that mine stock factors. No author or company is the subject.

## Subject

**RD-Agent(Q)** is Microsoft Research Asia's quant agent: it proposes factors and models, writes the code, backtests them and keeps the best. The repository (`microsoft/RD-Agent`) says that "at a cost under $10, RD-Agent(Q) achieves approximately 2× higher ARR than benchmark factor libraries". The paper is arXiv 2505.15155v2, NeurIPS 2025.

**QuantaAlpha** evolves factor-mining runs by mutation and crossover. Its repository's key result: best configuration (QuantaAlpha + GPT-5.2), CSI 300, test 2022–2025, ARR 4.68% and IR 0.6453. The paper is arXiv 2602.07085, three versions.

[Audit 014](014-cicc-loop-factor-engine.md) looked at a similar loop from CICC. Both papers here report information ratios computed from daily excess returns after costs. That is enough to recover a t-statistic: t = IR × √years.

## Three inputs

| Input | RD-Agent(Q), headline table | RD-Agent(Q), later table | QuantaAlpha |
|---|---|---|---|
| Knowledge cutoff | GPT-4o and o3-mini: Oct 2023 | GPT-4o: Oct 2023; o4-mini: Jun 2024 | GPT-5.2: Aug 2025; Claude Sonnet 4.5 and Gemini 3 Pro: Jan 2025; DeepSeek-V3.2, Qwen3: not published |
| Window | 2017-01 to 2020-08, CSI 300 | 2024-01 to 2025-06, CSI 500 and NASDAQ 100 | 2022-01 to 2025-12, CSI 300 |
| Attempts | 6 rows reported; 290 loops reported | 12 cells reported | 5 rows reported; 14 configurations |

## Finding

The counting rules were pre-registered and pushed before the scoring script ran (`docs/data/llm-alpha/LLM_ALPHA_PREREG.md`, commit `3b15648`). This is arithmetic on the authors' own figures. While choosing the subjects I had already worked out the main numbers by hand, and the pre-registration says so.

**The window behind RD-Agent(Q)'s "2×" lies entirely before both models' training cutoff. In the window after the cutoff, 0 of 12 reported results clear the bar. QuantaAlpha's best published configuration has t = 1.29, which would not clear the bar even for one configuration picked blind.**

| | Result | Bar | Clear |
|---|---|---|---|
| RD-Agent(Q), 2017–2020 (headline) | t 2.49 to 3.29 | — | Window seen in training: no verdict |
| RD-Agent(Q), 2024–2025 (after cutoff) | best t 2.66 (o4-mini, CSI 500) | 2.89 (N = 12) | **0 of 12** |
| QuantaAlpha v3, 2022–2025 | best t 1.29 (GPT-5.2) | 2.61 (N = 5) | **0 of 5**; 0 of 5 clear t = 2 |

- **RD-Agent(Q)'s headline window.** Table 1 tests on January 2017 to August 2020. GPT-4o and o3-mini both have an October 2023 cutoff (OpenAI's model pages). Prices are not shown to the agent, but what happened in those years, and which kinds of factor worked, can be in the model. The paper itself raised this and added a later window. On the headline window, the "2×" arithmetic holds (ARR 14.21% against 5.70% for Alpha 158).
- **After the cutoff.** On January 2024 to June 2025 the best of the 12 reported cells has t = 2.66. The bar for the best of 12 is 2.89. The paper concludes that the framework "remains unaffected by knowledge cutoff concerns"; its own numbers do not clear the bar for the configurations it reports. This means the evidence is insufficient. It does not mean the method has no edge.
- **QuantaAlpha.** All five backbones give t between 0.70 and 1.29. On the same window, the paper's own deep-learning baseline TRA has t 2.10, and it beats QuantaAlpha on IR, return and drawdown. The v3 text still describes QuantaAlpha as having "the strongest overall performance across most factor predictive power and strategy-level performance".

## The headline that changed

QuantaAlpha's first two versions (February and April 2026) reported, for the same row, the same market and the same test dates: **IR 3.33, ARR 27.75%**. Version 3 (May 2026) reports **IR 0.65, ARR 4.68%**.

| QuantaAlpha + GPT-5.2, CSI 300, 2022-01 to 2025-12 | v1 = v2 | v3 |
|---|---|---|
| IR | 3.33 | 0.65 |
| Annualised excess return | 27.75% | 4.68% |
| t (IR × √3.99 years) | 6.64 | 1.29 |

All 15 rows for the three LLM agents changed between v2 and v3; all baseline rows stayed the same. Three LLM rows are below zero in v3. Version 3 adds one sentence that is not in v2: for all LLM-based methods, "roughly 150 validated factors are submitted to the same downstream LightGBM model for final evaluation", "rather than from a single best factor". The paper does not say how the earlier numbers were produced. That the drop comes from this change in protocol is our inference.

The repository's README was updated to the new numbers on 2026-06-21.

## Where the loop looks

A search loop that keeps whatever backtests best is picking on the window it backtests. If that is the window later reported as the test, the test is not a test.

- **RD-Agent.** The default configuration in the repository (commit `484776c`) backtests every loop on 2017-01-01 to 2020-08-01, the headline window. The backtest's excess return, drawdown and IC go to the step that decides whether to "Replace Best Result". We have not checked that this code produced the paper's numbers. The paper reports at least 290 loops on that window. The bar for 290 is t = 3.78, above every headline row, even if the window had been unseen.
- **QuantaAlpha.** Its loop backtests on 2021 only, its validation year, and does not touch the 2022–2025 test window.

## How it was computed, and what is uncertain

**Data.**
- arXiv 2505.15155v2 and 2602.07085 v1, v2 and v3 (HTML), the two READMEs and the loop config files at the commits above, fetched 2026-11-19 14:50–15:05 UTC.
- The model developers' pages for cutoffs, fetched the same day.
- Raw files are kept outside the repository (arXiv licences). Their SHA-256 sums are in `docs/data/llm-alpha/2026-11-19/SHA256SUMS`. The rows were transcribed by script into `tables.json`.
- Script: `tools/llm_alpha_audit.py`. Results: `results.json`.

**Estimator.** IR = mean daily excess return over its standard deviation, times √252, as both papers define it. t = IR × √years is then the t-statistic of the mean daily excess return, on the normal scale. It ignores autocorrelation in daily returns. Years are counted from the papers' start and end dates.

**Bar.** Best of N, one-sided 2.275%, Bonferroni, as on every Evidence Deflator page. N is the number of results the paper reports on the same window. That is the narrowest count and the kindest to the authors.

**Level.** The IRs are the authors' figures from their papers (L2). We have no return series and recompute nothing but the arithmetic.

**Factor IC is a different question.** QuantaAlpha v3 also reports a daily-IC t-statistic of about 7 over 966 days, offered as ruling out data-snooping. That tests whether the factors correlate with next-day returns, not whether a strategy built on them earns its excess return after costs. It is not adjusted for how many factors were tried, and daily IC is autocorrelated. Not tested here.

**What is not tested.** Whether either method has an edge. Live or forward performance. AlphaAgent appears only as rows in QuantaAlpha's tables.

## What it would take

Report, next to each backtest, the model's training cutoff against the test window and how many configurations and loops were run on that window. Keep the loop off the window that is reported as the test. RD-Agent's later window is the right idea. Twelve configurations over eighteen months is not yet enough to clear the bar that comes with them.

For QuantaAlpha: say in the paper what changed between v2 and v3, and why.

Recheck: none scheduled. A new paper version, or a published post-cutoff run longer than eighteen months, would be grounds to reopen.
