# U.S. case study: decisions, status, and next steps

_Status updated 2026-07-30._

This is the authoritative running checklist for the U.S. analysis. Every
material methodological change should add or revise a dated decision here and
keep the remaining tasks current.

## Decisions implemented

| Decision | Rationale | Implementation |
|---|---|---|
| Name the health endpoint precisely | CDC PLACES measures ever-diagnosed depressive disorder, not strict current MDD | Report introduction and `docs/effect_size.md` |
| Retain Liu OR 0.931 (0.887–0.977) as primary | It is the prespecified published meta-analysis; post-hoc outcome selection can introduce judgment | `config.yaml` and model sensitivity |
| Convert OR to RR | InVEST applies a risk ratio; direct OR use exaggerates effects for a common outcome | `effect_size.py`, `compute_p0.py` |
| Define final U.S. p0 in the least-green stratum | p0 is conceptually the reference-group risk, not the overall mean | Lowest population-weighted national-urban NDVI quartile in `compute_p0.py` |
| Label p0=0.204 as interim and SF-derived | National NDVI completeness/QA is not finished; an SF mean is not a national reference risk | `baseline_risk_p0_method` in `config.yaml` |
| Do not average Perry outcome prevalences | PHQ-9, self-report, and health-record groups overlap | Separate 0.064, 0.096, 0.115 sensitivity scenarios |
| Re-pool one estimate per study only as sensitivity | Liu has 13 estimates from nine studies and high heterogeneity; selection is not neutral | `repool_liu_one_effect_per_study.py` |
| Eliminate national hard-coding | National cities must inherit the finalized RR | `src/national/run_city.py` reads `config.yaml` |
| Calibrate population totals | WorldPop is used for spatial allocation, but current SF adult sum is about 845k versus the 716,727 Census anchor | SF population builder and national county runner rescale to authoritative adult totals |
| Separate uncertainty types | Effect CI, p0 scenarios, and cost range answer different questions | Joint sensitivity table and revised report text |

## What is complete

- U.S. p0 calculator supports overall-interim and low-NDVI-reference methods.
- Perry outcome definitions are represented separately.
- OR × p0 × societal-cost sensitivity design is implemented.
- One-effect-per-study Liu robustness calculation is reproducible.
- The national city runner reads the configured effect size.
- Summary-report language distinguishes the modeled PLACES endpoint from MDD.
- The existing equity analysis, SVI extension, and multi-scenario comparison
  remain integrated.

## What remains to do

### Blocking the final national U.S. estimate

- [x] Identify the exact uploaded AOI: 1,167 unique county GEOIDs in
      `counties_gee.shp`.
- [ ] Re-export six missing expected counties: 21047, 21049, 21067, 21081,
      21103, and 21113.
- [ ] Resolve the 56 unexpected files from a different AOI vintage: either
      exclude them or revise and consistently regenerate the study universe.
- [ ] Re-export or defensibly harmonize the 467 expected rasters at 90 m; the
      specified standard is 30 m EPSG:5070.
- [ ] Finish all NDVI exports and resolve duplicate/failed Earth Engine tasks.
- [ ] Produce a manifest containing expected GEOID, file present, readable,
      CRS, pixel size, date, valid-pixel fraction, and value range.
- [ ] Re-export or exclude counties failing QA with a documented rule.
- [ ] Mosaic or aggregate national NDVI in a way that preserves tract-level
      population weighting.
- [ ] Build aligned national adult population and PLACES inputs.
- [ ] Fetch `config/adult_population.csv` from ACS and require complete county
      coverage; the current execution environment could not reach the Census API.
- [ ] Calculate and lock the lowest-NDVI-quartile p0.

### Required robustness and reporting

- [ ] Run all 12 OR × p0 combinations for the U.S. study domain.
- [ ] Regenerate the SF population raster with Census calibration and rerun all
      SF absolute case/cost outputs. The current report correctly flags a
      model-implied population about 17% above the Census anchor.
- [ ] Add 250/300/500/1,000 m exposure-radius sensitivity.
- [ ] Run and report the one-effect-per-study meta-analytic sensitivity.
- [ ] Verify the Perry citation and all transcribed counts against the paper.
- [ ] Decide whether the manuscript headline should retain “depression” or use
      “diagnosed depressive disorder” throughout.
- [ ] Propagate health-effect, p0, cost, and NDVI-input uncertainty without
      presenting structural scenarios as confidence intervals.
- [ ] Re-run all investment scenarios, advanced equity/SVI analysis, and report
      generation after the effect size is locked.
- [ ] Conduct national output QA: missing counties, extreme values, population
      reconciliation, duplicated GEOIDs, and scenario comparability.

### Manuscript-facing limitations to retain

- The exposure-response evidence is heterogeneous (Liu I² = 94.4%).
- Several forest-plot estimates come from the same underlying study.
- Zhang–Yu is an approximation for adjusted ORs.
- PLACES is self-reported ever diagnosis and includes depressive disorders
  beyond strict current MDD.
- The model estimates attributable/preventable prevalent cases under a
  counterfactual association; it is not a randomized intervention forecast.
- Geographic transportability can vary with vegetation type, urban form,
  population composition, healthcare diagnosis, and baseline prevalence.

## Completion criterion

The U.S. case is methodologically ready for manuscript use only when the
national NDVI manifest is complete, the low-NDVI reference p0 is locked,
all sensitivity/robustness runs are regenerated, and the national QA checklist
has no unexplained failures.
