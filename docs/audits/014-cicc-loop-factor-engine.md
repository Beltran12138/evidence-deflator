# Audit 014 · CICC's LLM loop factor-discovery engine (2026-10-20)

The subject is the reported evidence for the discovered factors, not the engineering of the loop or the research team.

## Subject

On 2026-08-03 CICC's research department (China International Capital Corporation) published *Large-model series (7): an automated factor-discovery engine based on Loop Engineering*, a system that searches for daily price-volume factors in China A-shares without human input. Our source is the summary CICC's own research account reposted on Sina Finance on 2026-08-05 (snapshot kept, md5 `2d05a20b…`); we have not read the full PDF.

The system runs as an agent loop of the kind Claude Code popularised: every five minutes a round generates 100 candidate factor expressions (25% mutation, 25% crossover, 15% parameter perturbation, 15% random, 20% written by an LLM from a list of 13 "mechanism families"), sub-agents and rules screen them, and a hard-coded backtest scores the survivors against 11 filters. A checkpoint file keeps "the hash set of factors already tested". The report's headline: after 581 rounds, **16,939 candidates tested, 69 kept (0.41%)**; the top five combined have an excess Sharpe of **3.14** and 18.3% annual excess return.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | The LLM behind the 20% of LLM-written candidates is not named, so its cutoff is unknown. The scored window (2025-01-01 to 2026-07-08) is recent enough that a model released by mid-2026 may have read about which A-share patterns worked in 2025; that cannot be ruled out. |
| Window | Factor values on the last 600 trading days (early 2024 to July 2026). **Every performance figure is stated for 2025-01-01 to 2026-07-08**, 553 days, 1.51 years. |
| Attempts | 16,939 candidates fully backtested; 58,100 generated (581 rounds × 100) before screening. |

## Finding

**No discovered factor clears the bar for the search that found it, and none of the reported performance is out of sample.** The window used to select the factors is the window used to report them: the filters require positive excess return in 2025 and in 2026 and a 2026 Sharpe above 0.5, and the results are then shown for 2025 and 2026.

- Method: t = Sharpe × √years on the report's own excess Sharpe ratios and its stated window (1.51 years). The bar for the best of N is Bonferroni, one-sided, as everywhere on this site.
- The system already records its own trial count. It does not use it: no figure in the report is adjusted for the 16,939 tries.

| What is reported | Excess Sharpe | t over 1.51 years |
|---|---|---|
| Top five combined (picked by Sharpe from the kept set; four flipped in sign) | 3.14 | 3.86 |
| Best single factor ("gap-trend divergence") | 2.74 | 3.37 |
| "Amplitude expansion and gap premium" | 2.64 | 3.25 |
| Average of the class representatives | 1.63 | 2.01 |
| Average of all 69 kept | 1.60 | 1.97 |
| Average of factors found after the dominant structure was banned | 0.92 | 1.13 |

| If the search counted as | Bar | Clears it |
|---|---|---|
| 16,939 backtested | 4.69 | none |
| 58,100 generated | 4.94 | none |
| 69 kept, the rejected ignored | 3.41 | only the top-five blend, which was itself picked from the 69 |

At the search's real size a factor would need an excess Sharpe of about 3.8 over this window. The candidates are far from independent (the report says the overnight-gap field appears in 85% of the kept factors, and 51 of the 69 were found in one 50-round burst), so the effective number of tries is smaller than 16,939 and the Bonferroni bar is too strict. But it is not 69: the rejected 16,870 were rejected by looking at the same 553 days.

## What the report says itself

- Its risk note: tested on history, "cannot ensure out-of-sample performance".
- It credits the 11 filters with avoiding the risk of the metric being fitted back (Goodhart's law). Filters scored on the reporting window are part of the fit, not a guard against it.
- It reports concentration honestly: overnight-gap factors dominate because they did best "in the 2025–2026 A-share environment", and the factors found later average a Sharpe of 0.92 against 1.68 for the core family.
- Two counts disagree inside the summary: the representatives are "21 classes" in one paragraph and "28" in the conclusion, with the same average Sharpe of 1.63.

## Why it matters beyond one report

This is the case the time and trial axes of this site were built for, at an institution's scale: an LLM agent loop that logs every candidate it tests, then reports the best of them without the count. Generating factors has become nearly free; the 16,939 tries took about three days. What did not get cheaper is the out-of-sample record that tells the best of them apart from the luckiest.

## Limits

- We read CICC's own summary, not the full report; the full PDF may contain a holdout we have not seen.
- Sharpe ratios are the report's, quoted, not recomputed; the factor expressions and return series are not public.
- The excess return is long top decile against the equal-weighted market with 0.1% one-way cost, as stated; we have not checked capacity or turnover.
- Converting Sharpe to t this way assumes weekly returns that are roughly independent; overlapping 5-day holdings would make the true t lower, not higher.

## What would fix it

Publish the kept factors' returns from 2026-07-09 onward, a window none of them was selected on, and report every Sharpe next to the number of candidates tested to find it. The loop already stores that number.

Recheck: when CICC publishes a follow-up with out-of-sample results, or after 2026-12-31 against any forward figures released by then.
