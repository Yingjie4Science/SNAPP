# Societal cost per case of depression — research note

Purpose: derive a defensible **annual societal cost per prevalent case of major
depressive disorder (MDD)** in the United States, in recent-year USD, to use as
the InVEST Urban Mental Health model's `health_cost_rate` (societal cost per
case). Scope requested: **full societal cost** (direct + indirect + suicide +
comorbidity), **US national**, recent-year USD.

## Bottom line

**Recommended `health_cost_rate` ≈ $22,000 per case (2024 USD).**
Sensitivity range: **~$17,000 (low) to ~$23,000 (high)**.

This is ~12× the direct-medical MEPS figure (~$1,848/treated case) because
medical treatment of depression itself is only about a tenth of its total
economic burden — workplace productivity losses dominate.

## Primary source

Greenberg PE, Fournier A-A, Sisitsky T, et al. **"The Economic Burden of Adults
with Major Depressive Disorder in the United States (2010 and 2018)."**
*PharmacoEconomics* 39:653–665 (2021). DOI
[10.1007/s40273-021-01019-4](https://doi.org/10.1007/s40273-021-01019-4)
([PMID 33950419](https://pubmed.ncbi.nlm.nih.gov/33950419/)). This is the
standard, peer-reviewed US economic-burden estimate and is comprehensive
(direct, workplace, and suicide-related costs), reported in **2020 US dollars**.

Key figures:

- **Total incremental economic burden of US adults with MDD:** $236.6 billion
  (2010) → **$326.2 billion (2018)**, a 38% increase (2020 USD).
- **Composition of the 2018 burden**
  ([APA summary](https://www.psychiatry.org/news-room/apa-blogs/the-economic-cost-of-depression-is-increasing),
  [Analysis Group](https://www.analysisgroup.com/Insights/publishing/the-economic-burden-of-adults-with-major-depressive-disorder-in-the-united-states-2010-and-2018/)):

  | Component | Share of total | Note |
  |---|---:|---|
  | Workplace (absenteeism + presenteeism) | 61% | dominant; rose from 48% in 2010 |
  | Direct medical — comorbid conditions | 24% | excess care for co-occurring illness |
  | Direct medical — MDD treatment itself | 11.2% | ≈ what MEPS measures |
  | Suicide-related | 4% | |

  "For every $1 of direct cost, an additional $2.30 is indirect."

## Deriving a per-case figure

Greenberg reports a national *total*, not a per-case value, so we divide by the
prevalent MDD population. In 2018, ~**17.5 million US adults** had MDD (NIMH: 17.7
million adults had a past-year major depressive episode,
[NIMH Major Depression](https://www.nimh.nih.gov/health/statistics/major-depression)).

    $326.2 billion ÷ 17.5 million ≈ $18,600 per prevalent case per year (2020 USD)

Inflation-adjust 2020 → 2024. Cumulative CPI-U was ~**+19.6%** (Jan 2020–Jan 2024,
[BLS/US Inflation Calculator](https://www.usinflationcalculator.com/)); using ~+20%:

    $18,600 × 1.20 ≈ $22,300 per case (2024 USD)  →  round to ~$22,000

### Per-case components (2024 USD)

| Component | Share | Per case (2024 USD) |
|---|---:|---:|
| Workplace productivity | 61% | ~$13,600 |
| Direct — comorbid conditions | 24% | ~$5,400 |
| Direct — MDD treatment | 11.2% | ~$2,500 |
| Suicide-related | 4% | ~$900 |
| **Total** | 100% | **~$22,300** |

## Reconciliation with the MEPS direct-medical figure

Our MEPS 2023 value — "mean expenditure per person **with care**" for depression,
~$1,438 (West) / ~$1,848 (national) — corresponds to the **MDD-treatment direct
slice only** (the 11.2% row above). Greenberg's implied per-case MDD-direct cost
(~$2,100 in 2020, ~$2,500 in 2024) is the same order of magnitude; the modest gap
reflects methodology (MEPS is condition-attributed household spending; Greenberg
uses claims-based incremental costs). The societal figure is ~12× larger because
it adds workplace losses (61%), comorbid medical care (24%), and suicide (4%),
which MEPS does not capture.

## Caveats (affect which number you pick)

- **Prevalence-based, per prevalent case, annual.** This matches the model, whose
  `risk_rate` is a prevalence and whose `preventable_cases` are prevalent cases.
  Do **not** use a per-*treated*-case denominator (only ~60% of cases are treated),
  which would inflate the figure.
- **Incremental / all-cause.** Greenberg's burden is the *excess* cost of people
  with MDD vs. without — appropriate for "cost avoided per case prevented."
- **Comorbidity attribution (24%) is debated.** If you attribute only costs
  directly tied to MDD (exclude the comorbid-care slice), the per-case figure
  drops to ~76% × $18,600 ≈ $14,200 (2020) ≈ **$17,000 (2024)** — the low end.
- **Not double-counted:** the four components above are mutually exclusive in
  Greenberg, so summing them is valid.
- **US national, not SF-specific.** SF wages/costs run above the US average, so
  the (wage-driven) workplace share would be somewhat higher locally; the US
  figure is conservative for SF.

## Recommendation for `health_cost_rate`

- **Central: $22,000** (2024 USD, full societal, per prevalent case).
- **Low: $17,000** (excludes comorbidity attribution).
- **High: $23,000** (full burden, upper inflation).

Run the model at the central value and re-run at the low/high bounds for a
sensitivity band on `preventable_cost`. If you prefer a purely conservative,
directly-observed number, keep the MEPS direct-medical value (~$1,848) — but
label results clearly as *healthcare savings only*, not societal.

## Sources

- [Greenberg et al. 2021, *PharmacoEconomics* (DOI)](https://doi.org/10.1007/s40273-021-01019-4) · [PubMed](https://pubmed.ncbi.nlm.nih.gov/33950419/) · [Analysis Group summary](https://www.analysisgroup.com/Insights/publishing/the-economic-burden-of-adults-with-major-depressive-disorder-in-the-united-states-2010-and-2018/)
- [APA: "The Economic Cost of Depression is Increasing; Direct Costs are Only a Small Part"](https://www.psychiatry.org/news-room/apa-blogs/the-economic-cost-of-depression-is-increasing)
- [NIMH Major Depression statistics](https://www.nimh.nih.gov/health/statistics/major-depression)
- [BLS Consumer Price Index](https://www.bls.gov/cpi/) · [cumulative CPI 2020–2024](https://www.usinflationcalculator.com/)
- MEPS-HC Medical Conditions (2023), `data/urban-mental-health/raw/meps/` — direct-medical comparison
