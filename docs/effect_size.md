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

### Interim operational value

Until all national NDVI exports pass completeness and quality checks, the
pipeline uses `p0 = 0.204`, the overall adult-population-weighted PLACES
prevalence calculated from the current **San Francisco** inputs. `config.yaml`
labels this `sf_overall_population_weighted_places_interim`; it is neither a
national U.S. estimate nor the final least-green reference risk.

```bash
# Current SF diagnostic; does not overwrite the national configuration
python src/inputs/compute_p0.py --no-write

# Final U.S. primary calculation once national inputs are complete
python src/inputs/compute_p0.py \
  --reference lowest-ndvi-quantile --quantile 0.25 \
  --prevalence <national_places_layer> \
  --population <national_adult_population_raster> \
  --ndvi <national_baseline_ndvi_mosaic>
```

### Perry values: sensitivity only

Perry et al. (2019) report three outcome-specific prevalences in the lowest
NDVI quartile:

| Outcome | p0 |
|---|---:|
| PHQ-9 ≥10 | 0.064 |
| Self-reported doctor diagnosis | 0.096 |
| Health-record diagnosis | 0.115 |

These groups overlap, so their percentages must **not be summed or averaged**.
They are separate sensitivity scenarios. The health-record definition is the
closest of the three to PLACES, but it comes from one Canadian cohort and
cannot serve as the primary national U.S. reference risk.

### Local implementation check

The low-NDVI estimator was tested on the current SF files without changing the
configuration. Overall population-weighted p0 was **0.2039**; the lowest
population-weighted NDVI quartile gave **0.2058**, using an NDVI threshold of
0.1771, 67 of 241 tracts, 215,883 adults in the selected stratum, and 99.98%
NDVI population coverage. This validates the computation and shows little local
sensitivity, but it is not evidence for the final national p0.

The current model grid crosses the three Liu OR values with the configured
interim SF p0 and all three Perry p0 values. After the national p0 is locked,
the same grid must be regenerated with that value:

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
4. Use overall population-weighted PLACES prevalence only as an explicitly
   interim operational value.
5. Keep Perry's 0.064, 0.096, and 0.115 as separate scenarios; do not average.
6. Treat one-effect-per-study re-pooling as robustness analysis.
7. Read the effect size from `config.yaml` in both city and national runners.
8. Use WorldPop for within-area population allocation but calibrate each adult
   raster to an authoritative Census/ACS adult total before calculating cases.

## To-do before the U.S. analysis is final

- [ ] Complete and QA all national county NDVI exports.
- [ ] Build the national-urban NDVI mosaic and aligned adult-population and
      PLACES tract inputs.
- [ ] Calculate the primary low-NDVI-quartile p0 and save its threshold,
      selected population, tract count, and coverage.
- [ ] Recompute central and confidence-limit RRs in `config.yaml`.
- [ ] Re-run the OR × p0 × cost sensitivity grid and summary report.
- [ ] Run exposure-radius sensitivity (at minimum 250, 300, 500, and 1,000 m).
- [ ] Report the one-effect-per-study robustness result beside, not instead of,
      the published pooled estimate.
- [ ] Add causal-language and outcome-definition caveats to the manuscript.

## Sources

- Liu, Z., et al. (2023). *Green space exposure on depression and anxiety
  outcomes: A meta-analysis*. Environmental Research, 231, 116303.
  https://doi.org/10.1016/j.envres.2023.116303
- Zhang, J., & Yu, K. F. (1998). What's the relative risk? JAMA, 280, 1690–1691.
  https://doi.org/10.1001/jama.280.19.1690
- Perry et al. (2019), as identified in the Liu et al. meta-analysis; verify the
  final bibliographic record and Table 1 transcription before submission.
