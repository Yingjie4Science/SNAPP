# Exposure-response, baseline risk, and exposure radius

This document records the U.S. case-study decisions that control the
greenness-to-depression calculation. It should be read with
[`us_case_status.md`](us_case_status.md).

## Outcome represented by the model

The baseline raster is CDC PLACES **DEPRESSION**: the percentage of adults who
report ever being told by a health professional that they had a depressive
disorder. It is not strict current major depressive disorder (MDD) prevalence
and is not interchangeable with PHQ-9 ≥10. Results and figure legends should
therefore say “PLACES-defined diagnosed depressive disorder” on first use.

## Published exposure-response estimate

Liu et al. (2023) report a pooled **odds ratio (OR) of 0.931 (95% CI
0.887–0.977) per +0.1 NDVI** for depression. The forest plot contains 13
estimates from nine unique studies; Perry contributes three outcomes, Abraham
two, and Gonzales two. The reported heterogeneity is high (I² = 94.4%).

The published pooled OR remains the primary estimate because selecting one
outcome per study after seeing the forest plot involves judgment. A scripted,
one-effect-per-study re-pooling is retained as a robustness analysis:

```bash
python src/analysis/repool_liu_one_effect_per_study.py
```

The input transcription and selection rationale are in
`config/liu_2023_ndvi_depression_effects.csv`. This sensitivity is not presented
as a superior replacement for Liu's prespecified meta-analysis.

## Why the OR is converted

InVEST applies `effect_size` as a risk ratio (RR):

```text
preventable_cases =
  (1 - exp(ln(effect_size) * 10 * delta_NDVI)) * baseline_cases
```

Using an OR directly for a common outcome exaggerates the protective effect.
The Zhang–Yu conversion is:

```text
RR = OR / (1 - p0 + p0 * OR)
```

where `p0` is the outcome risk in the reference, least-green population.

## Decision on p0

### Primary U.S. estimand

The primary p0 will be the adult-population-weighted PLACES prevalence among
tracts in the **lowest population-weighted quartile of baseline NDVI across the
national urban study domain**:

```text
p0 = sum(adult_population_i * PLACES_prevalence_i) /
     sum(adult_population_i), for low-NDVI reference tracts
```

The NDVI threshold is itself population weighted. This definition matches the
reference exposure concept while keeping the outcome definition identical to
the modeled prevalence surface.

### Locked national value

The completed national calculation gives **p0 = 0.191045** among tracts in the
lowest adult-population-weighted NDVI quartile (threshold mean NDVI =
**0.416390**) across all 1,167 study counties. The resulting primary RR is
**0.943436** (OR-CI conversion: 0.906571–0.981312). Full inputs, coverage, and
the Florida temporal bridge are documented in
`results/summaries/national_p0.md`.

```bash
# Optional SF diagnostic; does not overwrite the national configuration
python src/inputs/compute_p0.py --no-write

# Reproduce the locked national calculation
python src/national/compute_national_p0.py \
  --prevalence <national_places_layer> \
  --population <national_worldpop_raster>
```

### Hystad et al. (2019; “Perry”): sensitivity only

Hystad et al. (2019) report three outcome-specific prevalences in the lowest
NDVI quartile:

| Outcome | Count | p0 |
|---|---:|---:|
| PHQ-9 ≥10 | 130 | 0.064 |
| Self-reported doctor diagnosis | 192 | 0.096 |
| Health-record diagnosis | 234 | 0.115 |

These groups overlap, so their percentages must **not be summed or averaged**.
They are separate sensitivity scenarios. Row-specific denominators may differ
because of missing data, so the printed percentages should not be reverse
engineered into a common denominator. The health-record definition is the
closest of the three to PLACES, but it comes from one Canadian cohort and
cannot serve as the primary national U.S. reference risk.

The bibliographic record and Table 1 transcription are documented in
[`perry_2019_verification.md`](perry_2019_verification.md). The correct
author-date citation is **Hystad et al. (2019)**; “Perry” is the first author's
given name.

### Local implementation check

The low-NDVI estimator was tested on the current SF files without changing the
configuration. Overall population-weighted p0 was **0.2039**; the lowest
population-weighted NDVI quartile gave **0.2058**, using an NDVI threshold of
0.1771, 67 of 241 tracts, 215,883 adults in the selected stratum, and 99.98%
NDVI population coverage. This validates the computation and shows little local
sensitivity, but it is not evidence for the final national p0.

The current model grid crosses the three Liu OR values with the locked national
p0 and all three Hystad et al. p0 sensitivity values:

```bash
python src/urban_mental_health/run_sensitivity.py
```

## Interpretation of the uncertainty

- The Liu OR confidence limits, converted at the configured p0, form the
  conditional statistical effect-size interval.
- The alternative p0 values are structural/outcome-definition scenarios, not a
  confidence interval.
- The $17,000–$23,000 societal cost-per-case range is an economic scenario
  range, not a confidence interval.
- High meta-analytic heterogeneity and repeated outcomes mean the pooled OR
  should be interpreted as a transportable average association, not a
  universal causal constant.

## Exposure radius

The model retains a 300 m radius. Liu pools studies using several residential
buffers, commonly 250–1,000 m, so no single buffer is uniquely implied by the
meta-analysis. Three hundred metres is near the common 250–500 m neighborhood
scale and preserves within-city spatial contrast at 30 m NDVI resolution.
Radius sensitivity remains a required U.S. robustness test.

## Decisions recorded

1. Keep Liu's published pooled OR as the primary exposure-response estimate.
2. Convert OR to RR; never pass the OR directly to InVEST.
3. Use the lowest population-weighted national-urban NDVI quartile for the
   final U.S. p0.
4. Retain the former overall population-weighted PLACES prevalence only as a
   superseded diagnostic.
5. Keep Hystad's 0.064, 0.096, and 0.115 as separate scenarios; do not average.
6. Treat one-effect-per-study re-pooling as robustness analysis.
7. Read the effect size from `config.yaml` in both city and national runners.
8. Use WorldPop for within-area population allocation but calibrate each adult
   raster to an authoritative Census/ACS adult total before calculating cases.

## Remaining to-do

- [x] Complete national multi-scenario runs.
- [x] Complete national exposure-radius runs and final QA.
- [ ] Archive exact input dataset versions and software environment.
- [ ] Add the documented causal-language and outcome-definition caveats to the
      submitted manuscript text.

## Sources

- Liu, Z., et al. (2023). *Green space exposure on depression and anxiety
  outcomes: A meta-analysis*. Environmental Research, 231, 116303.
  https://doi.org/10.1016/j.envres.2023.116303
- Zhang, J., & Yu, K. F. (1998). What's the relative risk? JAMA, 280, 1690–1691.
  https://doi.org/10.1001/jama.280.19.1690
- Hystad, P., Payette, Y., Noisel, N., & Boileau, C. (2019). *Green space
  associations with mental health and cognitive function: Results from the
  Quebec CARTaGENE cohort*. Environmental Epidemiology, 3(1), e040.
  https://doi.org/10.1097/EE9.0000000000000040
