# Societal cost per case of depression — pooled research synthesis

Purpose: derive a defensible **annual societal cost per prevalent case of major
depressive disorder (MDD)** in the US, recent-year USD, for the InVEST Urban
Mental Health model's `health_cost_rate`. Scope: **full societal** (direct +
indirect + suicide + household), **US national**. This note pools multiple
cost-of-illness studies rather than relying on a single one, and cross-validates
across independent base years.

## Bottom line

**Recommended `health_cost_rate` ≈ $21,000 per case (2024 USD)** — the pooled
mean of the two most recent US burden studies.
Sensitivity range: **~$17,000 (low) to ~$23,000 (high)**.

Independent estimates converge within ~12%, which gives reasonable confidence.

## Approach (how this was produced)

1. **Literature search** via research connectors (scite/Consensus-style
   `search_literature`; Elicit `search_papers`) plus web search. Queries covered
   "economic burden of MDD United States", "cost of illness depression per
   person", workplace/productivity cost, and systematic reviews/meta-analyses.
2. **Inclusion:** US national incremental (excess) cost-of-illness studies for
   adults with MDD that report a total burden and the prevalent population, so a
   per-case figure can be derived; plus one worldwide meta-analysis and one
   multi-country workplace study for convergent validation.
3. **Per-case derivation:** per case = total incremental burden ÷ number of US
   adults with MDD (prevalence-based, per *prevalent* case — matching the model).
4. **Inflation:** adjusted to 2024 using BLS CPI-U annual averages
   (2020 = 258.811 … 2024 = 313.689).
5. **Pooling:** simple mean of the per-case estimates from the two most recent,
   methodologically-comparable studies (2018 and 2019 base years). A third
   (2010) vintage is used as a convergence check.

## Data collected (studies pooled)

| # | Study (source) | Base yr | Total burden | US adults w/ MDD | Per case (as-reported) | Per case (2024 USD) |
|---|---|---|---|---:|---|---:|
| 1 | Greenberg et al. 2015, *J Clin Psychiatry* ([10.4088/jcp.14m09298](https://doi.org/10.4088/jcp.14m09298)) | 2010 | $210.5B (2012$) | 15.5M | ~$13,600 (2012$) | ~$18,600 |
| 2 | Greenberg et al. 2021, *PharmacoEconomics* ([10.1007/s40273-021-01019-4](https://doi.org/10.1007/s40273-021-01019-4)) | 2018 | $326.2B (2020$) | 17.5M | ~$18,640 (2020$) | **~$22,600** |
| 3 | Greenberg et al. 2023, *Advances in Therapy* ([10.1007/s12325-023-02622-x](https://doi.org/10.1007/s12325-023-02622-x)) | 2019 | $333.7B (2019$) / $382.4B (2023$) | 19.8M | **$16,854 (2019$)** | **~$19,900** |

Convergent (not pooled into the dollar figure):

- **König et al. 2019/2020, *Epidemiol Psychiatr Sci*** — "The excess costs of
  depression: a systematic review and meta-analysis" (48 studies;
  [10.1017/s2045796019000180](https://doi.org/10.1017/s2045796019000180)).
  Depression vs. no-depression **ratio of means**: direct costs **2.58**
  (95% CI 2.01–3.31), indirect costs **2.28** (1.75–2.98) in adults. Confirms
  depression roughly 2–3× both direct and indirect costs — consistent with the
  large incremental per-case figures above.
- **Evans-Lacko & Knapp 2016, *Soc Psychiatry Psychiatr Epidemiol*** — workplace
  absenteeism + presenteeism costs across 8 countries incl. the US
  ([10.1007/s00127-016-1278-4](https://doi.org/10.1007/s00127-016-1278-4)),
  corroborating the dominant workplace share.

## Cross-validation

Per-case, inflation-adjusted to **2024 USD**:

| Anchor | Per case (2024 USD) |
|---|---:|
| Greenberg 2018 base (study 2) | $22,592 |
| Greenberg 2019 base (study 3) | $19,882 |
| Greenberg 2010 base (study 1, check) | ~$18,600 |
| **Pooled mean (studies 2 & 3)** | **≈ $21,240** |

The 2018 vs 2019 spread (~$2,700) is driven mainly by the **denominator**
(19.8M adults in 2019 vs 17.5M in 2018 grew faster than the total), not by a real
cost jump. Averaging them is the cross-validated central estimate. The older 2010
vintage lands in the same band, confirming stability.

`estimate_health_cost.py` prints all anchors so you can see the spread, and
`--anchor greenberg2018|greenberg2019|pooled` selects the basis (default pooled).

## Composition (two taxonomies)

Greenberg **2018** four-way split (used by the script's component breakdown):
workplace 61% · comorbid-medical 24% · MDD-treatment 11.2% · suicide 4%.

Greenberg **2019** update reports a finer split: healthcare **38.1%**,
household-related **24.0%**, presenteeism **13.0%**, absenteeism **11.5%**, with
the remainder in unemployment/disability and suicide-related. (Notably ~40% of
indirect costs fall on *household members*, and MDD was attributed ~30,900 of the
45,861 US suicides in 2019.) Both agree the majority is **non-medical**.

Per-case components at the pooled ~$21,240 (2024 USD), Greenberg-2018 shares:

| Component | Share | Per case |
|---|---:|---:|
| Workplace productivity | 61% | ~$12,955 |
| Direct — comorbid conditions | 24% | ~$5,097 |
| Direct — MDD treatment | 11.2% | ~$2,379 |
| Suicide-related | 4% | ~$850 |

(Shares carry Greenberg's ~0.2% rounding; written to `health_cost_components.csv`.)

## Reconciliation with MEPS

Our MEPS 2023 direct-medical figure (~$1,438 West / $1,848 national, per treated
case) maps to the **MDD-treatment slice only** (~11%). The Greenberg-implied
MDD-treatment per case (~$2,400, 2024 USD) is the same order of magnitude; the
societal total is ~10–12× larger because workplace, comorbid-medical, household,
and suicide costs — which MEPS does not measure — dominate.

## Caveats

- **Prevalence-based, per prevalent case, annual** — matches the model.
- **Incremental / all-cause** (excess vs. non-MDD) — appropriate for "cost
  avoided per case prevented".
- **Comorbidity/household attribution (~24%) is debatable**; excluding it gives
  the ~$17,000 low bound.
- **Single research group.** The Greenberg/Analysis Group series dominates US MDD
  burden estimates; the König meta-analysis and Evans-Lacko workplace study are
  independent and concordant, but a truly independent US dollar per-case estimate
  is scarce — treat the range, not the point, as the finding.
- **US national**, not SF-specific; SF's higher wages push the 61% workplace
  share up (use `estimate_health_cost.py --wage-factor`).

## Recommendation

- **Central: ~$21,000** (2024 USD; `--anchor pooled`, the default).
- **Low: ~$17,000** (exclude comorbidity/household attribution).
- **High: ~$23,000** (Greenberg-2018 basis, upper inflation).

Run the model at the central value and re-run at low/high for a sensitivity band
on `preventable_cost`. Use `--basis direct` (~$1,848) only if you explicitly want
*healthcare-only* savings.

## Sources

- Greenberg et al. 2015 — [J Clin Psychiatry (DOI)](https://doi.org/10.4088/jcp.14m09298) · [PubMed](https://pubmed.ncbi.nlm.nih.gov/25742202/)
- Greenberg et al. 2021 — [PharmacoEconomics (DOI)](https://doi.org/10.1007/s40273-021-01019-4) · [PubMed](https://pubmed.ncbi.nlm.nih.gov/33950419/)
- Greenberg et al. 2023 — [Advances in Therapy (DOI)](https://doi.org/10.1007/s12325-023-02622-x) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10499687/)
- König et al. 2019 meta-analysis — [Epidemiol Psychiatr Sci (DOI)](https://doi.org/10.1017/s2045796019000180) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8061284/)
- Evans-Lacko & Knapp 2016 — [Soc Psychiatry Psychiatr Epidemiol (DOI)](https://doi.org/10.1007/s00127-016-1278-4)
- [NIMH Major Depression statistics](https://www.nimh.nih.gov/health/statistics/major-depression) · [BLS CPI](https://www.bls.gov/cpi/)
- MEPS-HC Medical Conditions 2023 — `data/urban-mental-health/raw/meps/`
