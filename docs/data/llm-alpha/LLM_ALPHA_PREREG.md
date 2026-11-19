# Pre-registration · LLM factor-mining agents against the luck bar: RD-Agent(Q) and QuantaAlpha (2026-11-19)

## What kind of test this is

This is retrospective arithmetic on figures the authors published, the same kind as audit 013. It is not a blind test. While choosing the subjects I multiplied several reported information ratios by the square root of the test length by hand, so I already know roughly where the main numbers fall (listed below). This file fixes the subjects, the rows, the counting of N, the arithmetic and the wording before the script `tools/llm_alpha_audit.py score` is run, so that none of those can be chosen after seeing its output.

## The claims

- **RD-Agent(Q)**, Microsoft Research Asia, `microsoft/RD-Agent` (README at commit `484776c`), paper arXiv 2505.15155v2 (NeurIPS 2025). README: "at a cost under $10, RD-Agent(Q) achieves approximately 2× higher ARR than benchmark factor libraries while using over 70% fewer factors." The paper (D.1) adds a later test window and says the framework "remains unaffected by knowledge cutoff concerns".
- **QuantaAlpha**, `QuantaAlpha/QuantaAlpha` (README at commit `b7ceb27`), paper arXiv 2602.07085 (v1 2026-02-06, v2 2026-04-22, v3 2026-05-18). README key results, "best configuration (QuantaAlpha + GPT-5.2), CSI 300, test 2022–2025": IC 0.0472, ARR 4.68%, IR 0.6453. The v3 text says QuantaAlpha "achieves the strongest overall performance across most factor predictive power and strategy-level performance".

The subject is these published claims. No author or company is the subject.

## What we have seen before writing this

Fetched 2026-11-19 14:50–15:05 UTC; raw files kept outside the repository (arXiv licences), SHA-256 sums in `2026-11-19/SHA256SUMS`: the two arXiv abstract pages, 2505.15155v2 HTML, 2602.07085 v1/v2/v3 HTML, both READMEs at the commits above, RD-Agent's `qlib_rd_loop/conf.py`, `factor_template/conf_combined_factors.yaml` and `developer/feedback.py` at `484776c`, QuantaAlpha's `configs/backtest.yaml` and `factors/factor_template/conf_combined_factors.yaml` at `b7ceb27`.

The reported rows, transcribed by `tools/llm_alpha_audit.py extract` and checked against the text by hand, are in `2026-11-19/tables.json`.

Already seen, by hand, before writing:
- RD-Agent(Q) Table 2 (2024-01-01 to 2025-06-30): the largest IR is 2.17 (R&D-Agent(Q), o4-mini, CSI 500), about t 2.66; I compared it with bar(12) = 2.89.
- QuantaAlpha v3 GPT-5.2: IR 0.6453 over about four years, about t 1.29.
- RD-Agent(Q) Table 1 (2017-01-01 to 2020-08-01): best IR 1.74, about t 3.29.
- QuantaAlpha v1 and v2 Table 1 report, for the same row (GPT-5.2, CSI 300, same test dates), IR 3.3251 and ARR 27.75%; v3 reports IR 0.6453 and ARR 4.68%. Baseline rows (TRA, Alpha158, Alpha360) are the same in v2 and v3. A search of the v3 text for an explanation found none; the README commit `6eb78a1` (2026-06-21) says "Update README results and figures to match arXiv v2" and gives the v3 numbers.
- RD-Agent's default loop config (`conf.py` at `484776c`) sets the test segment and the backtest to 2017-01-01 to 2020-08-01, the window of Table 1, and `feedback.py` passes the backtest's annualised excess return, max drawdown and IC to the step that decides "Replace Best Result". QuantaAlpha's in-loop config (`conf_combined_factors.yaml` at `b7ceb27`) backtests on 2021 only, its validation year, not its test window.

## Estimator

Both papers define IR as the mean daily excess return (after costs) over its standard deviation, times √252. Then t = IR × √years is the t-statistic of the mean daily excess return, on the normal scale, ignoring autocorrelation.

years = (end − start + 1 day) / 365.25, with the start and end dates each paper gives:

| Window | Start | End | Years |
|---|---|---|---|
| RD-Agent(Q) Table 1 | 2017-01-01 | 2020-08-01 | 3.58 |
| RD-Agent(Q) Table 2 | 2024-01-01 | 2025-06-30 | 1.50 |
| QuantaAlpha Table 1 | 2022-01-01 | 2025-12-26 | 3.99 |

t is rounded to two decimals. The bar is `bar(N)` from `src/hl_wallet.py`: one-sided 2.275%, Bonferroni, the same as on every Evidence Deflator page. The IRs are the authors' (level L2: figures in a paper). We have no return series and do not recompute them.

## Knowledge cutoff rule

A test window that lies before a model's training cutoff was, as far as anyone can tell, in that model's training data. Prices in the window are not shown to the model, but what happened in those years, and which kinds of factor worked, can be. For each backend we use the cutoff in the developer's documentation, or the date the paper itself states. Where neither is available we write "not published" and the window cannot be ruled out as seen. We report the share of each window that lies before each backend's cutoff.

Cutoffs used:
- GPT-4o 2023-10-01 and o4-mini 2024-06-01, as stated in 2505.15155v2 D.1.
- o3-mini 2023-10, from a secondary source. The only thing that matters here is that it falls after 2020-08-01.
- GPT-5.2 2025-08-31, OpenAI model comparison as quoted by secondary sources. To be checked against an OpenAI page before the audit page goes up; if the date differs, the share is recomputed and the change noted.
- Claude Sonnet 4.5, Gemini 3 Pro, DeepSeek-V3.2 and Qwen3-235B: looked up on results day from each developer's documentation, or written "not published".

## Primary tests

**P1 · RD-Agent(Q) headline window (Table 1, CSI 300, 2017-01-01 to 2020-08-01).** If the whole window lies before the cutoff of every backend in Table 1, we say: the window that carries the "2×" claim was inside the training data of both models, so Table 1 is not evidence of out-of-sample skill either way. The t values are reported with no verdict.

**P2 · RD-Agent(Q) after the cutoff (Table 2, 2024-01-01 to 2025-06-30).** N = 12, the six R&D-Agent rows × two markets as reported. Bar(12) = 2.89. We count the cells that clear it.
- Our critique fails if at least one cell clears bar(12). We then say on the audit page that RD-Agent(Q)'s post-cutoff results clear the bar for the configurations it reports.
- If none clears, we say the post-cutoff evidence does not clear the bar for the 12 configurations reported, and the evidence is insufficient. We do **not** say the method has no edge.

**P3 · QuantaAlpha v3 (Table 1, CSI 300, 2022-01-01 to 2025-12-26).** N = 5, the five QuantaAlpha rows (one per backbone) the paper reports. Bar(5) = 2.61. We count the rows that clear it, and the rows that clear 2 (one configuration picked blind).
- Our critique fails if any row clears bar(5).
- If none clears 2, we say the published best configuration does not clear the bar for a single test.

Expectation, written knowing the hand arithmetic above: P1 the whole window is before every cutoff; P2 0 of 12 clear; P3 0 of 5 clear, and 0 of 5 clear 2.

## Reported with no pass mark

- **N under wider counts.** N_paper is every configuration of the subject's own method that the paper reports on the same window (Table 1, backend comparison, ablations), counted by name on results day. N_loop is, for RD-Agent(Q) only, the loops whose backtest ran on the reported test window under the default config: at least the 6 backends × 30 loops of its Fig. 9 plus the 33 + 33 + 44 loops of its Table 3. The bar is given for each count.
- **Which data the loop sees.** Whether the loop that picks factors backtests on the reported test window, per the code at the commits above. Caveat: we have not verified that this code is what produced the paper's numbers.
- **QuantaAlpha versions.** Every Table 1 row that changed between v2 and v3, as IR and ARR before and after. Whether v1 and v2 are identical.
- **QuantaAlpha against its own baselines in v3.** t of TRA, Alpha158 and Alpha360 on the same window, next to the claim "strongest overall … strategy-level performance".
- **RD-Agent(Q) "2×".** ARR of R&D-Agent(Q) against Alpha 158 and Alpha 360 in Table 1, as the arithmetic behind the README sentence.
- **Cutoff shares** for each QuantaAlpha backbone over 2022-01-01 to 2025-12-26.

## Not tested

- Whether either method has an edge. We only ask whether the published evidence clears the bar it needs.
- Live or forward performance. No forward reading is set: we have no A-share data feed in this project.
- AlphaAgent (KDD 2025) as a subject in its own right. It appears only as a row in QuantaAlpha's tables. The GitHub repository found under that name was not matched to the paper.

## Not done after this file is committed

No change to the subjects, the rows, N for P2 and P3, the years, the bar, the cutoffs used for P1 and P2, or the wording rules above. If a number in `tables.json` turns out to be mis-transcribed, it is corrected from the saved HTML and the correction is listed under Results. It is not dropped.
