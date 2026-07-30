# U.S. case study: decisions, status, and remaining work

_Authoritative status updated 2026-07-30._

## Decisions locked

| Decision | Rationale | Implementation/evidence |
|---|---|---|
| Report the endpoint as PLACES-defined diagnosed depressive disorder | PLACES measures ever diagnosis among adults, not strict current MDD | `docs/effect_size.md`; report text |
| Retain Liu et al. OR 0.931 (0.887–0.977) | Prespecified published meta-analysis; one-effect-per-study result is robustness only | `config.yaml`; sensitivity table |
| Convert OR to RR | InVEST requires an RR and the outcome is common | `effect_size.py`; `compute_national_p0.py` |
| Define p0 in the national least-green stratum | p0 is the reference-group risk, not overall prevalence | Lowest adult-population-weighted NDVI quartile |
| Lock p0 = 0.191045 | Outcome, adults, AOI, and exposure distribution match the model | `results/summaries/national_p0.md` |
| Do not average Hystad outcome prevalences | PHQ-9, self-report, and health-record groups overlap | Separate 0.064/0.096/0.115 sensitivities |
| Use WorldPop only for spatial allocation | WorldPop reprojection is not count preserving | Exact county scaling to ACS 2023 adults |
| Harmonize all NDVI at 90 m | A common 90 m grid avoids mixed resolution; 30 m sources are area-averaged | `harmonize_ndvi_resolution.py` |
| Quarantine, do not delete, out-of-AOI files | Preserves provenance while locking the active study universe | `data/national/ndvi/_outside_current_aoi` |
| Bridge Florida with official PLACES 2022 only | PLACES 2023 has null depression values for all Florida tracts | `config/places_florida_2022.csv` |
| Use SVI alongside income | Income alone is an incomplete equity construct | SF tract and national county analyses |
| Keep uncertainty types separate | Effect CI, p0 definitions, cost bounds, radius, and scenarios answer different questions | Results tables and legends |

## Completed

- [x] Re-exported the six missing Kentucky counties.
- [x] Moved 56 out-of-AOI rasters to a separate quarantine subfolder.
- [x] Harmonized all 1,167 active rasters to aligned 90 m EPSG:5070 grids.
- [x] Strengthened the audit to reject unmasked `NaN`/infinite cells.
- [x] Passed the full-read NDVI audit: 1,167 present, 0 missing, 0 unexpected,
      0 QA failures.
- [x] Fetched and validated complete ACS 2023 adult targets for all counties.
- [x] Fetched and validated official CDC/ATSDR 2022 county SVI for all counties.
- [x] Calibrated SF population to 716,727 adults and reran every SF scenario.
- [x] Locked national p0 and the central/boundary RRs in `config.yaml`.
- [x] Verified Hystad et al. (2019) bibliographic details and Table 1 counts.
- [x] Reran SF OR × p0 × cost, exposure-radius, income, SVI, ICE, spatial,
      and allocation analyses.
- [x] Completed the national primary and alternative greening scenarios for
      all 1,167 counties.
- [x] Added national county-level SVI concentration and slope-index analysis
      with 1,000-draw bootstrap intervals.
- [x] Completed national 250/300/500/1,000 m exposure-radius sensitivity.
- [x] Added resumable per-county processing, cached-input scenario runs, and
      fail-closed national final QA.
- [x] Passed final QA for all four national scenarios and all four radii.
- [x] Archived exact platform package versions and SHA-256 checksums for the
      locked AOI and analysis inputs.
- [x] Added automated CI checks for manifest completeness, ACS reconciliation,
      finite outputs, and committed national QA.

## Key locked values

- National p0: **0.191045**
- Population-weighted low-NDVI threshold: **0.416390**
- Eligible/reference tracts: **59,161 / 14,993**
- ACS adults represented: **218,643,229**
- Adults with valid NDVI: **218,607,899 (99.9838%)**
- RR per +0.1 NDVI: **0.943436** (0.906571–0.981312)
- SF uniform +0.05 central result: about **4,170 cases/year** and
  **$88.7M/year** (exact report regenerates from the locked configuration).
- National uniform +0.05 central result: **1,264,304 cases/year** and
  **$26.90B/year** after enforcing the no-decrease NDVI cap.
- National radius sensitivity: **1,264,303 / 1,264,304 / 1,241,075 /
  1,217,851 cases/year** at 250 / 300 / 500 / 1,000 m, respectively.

## Important QA incident and resolution

The first national aggregation produced valid totals only for 14 Kentucky
counties. Diagnosis showed that older harmonized rasters declared `-9999` as
nodata but retained internal `NaN` cells; convolution therefore propagated
non-finite results. The preliminary 8,171-case national figure was rejected.
Harmonization now explicitly converts every non-finite source/destination cell
to the declared nodata value, and the audit counts unmasked non-finite cells.
The full 1,167-file audit and all national primary runs were repeated.

A second fail-closed check found small negative benefits in 10 greenable-only
county runs. The shared NDVI cap had lowered baseline pixels already above
0.90, inadvertently modeling vegetation removal. Scenario construction now
preserves every baseline value above the cap and caps only proposed increases.
All SF and national scenarios were rerun; the corrected national tables contain
1,167 finite, strictly positive county totals in every scenario.

## Manuscript-facing limitations to retain

- Liu meta-analytic heterogeneity is high (I² = 94.4%), and multiple estimates
  come from the same underlying studies.
- Zhang–Yu is an approximation for adjusted ORs, although error is small here
  because the OR is close to 1.
- PLACES is self-reported ever diagnosis and is broader than current MDD.
- Results are prevalence-based modeled counterfactuals, not incidence effects
  or randomized intervention forecasts.
- Florida PLACES values use a transparent one-release temporal bridge.
- Harmonized 90 m NDVI cannot restore spatial detail absent from original 90 m
  exports.
- National county SVI masks within-county inequity.
- A flat cost per case does not reflect local wage variation in productivity
  losses.
- SF NDVI does not fully cover the northern/eastern search-radius buffer;
  99.98% of modeled adult population is covered, but an edge-effect limitation
  remains.

## Remaining to-do

- [ ] Decide whether to finish the optional national existing-greenness
      accounting counterfactual; SF already includes this comparison.
- [ ] Decide whether regional wage-adjusted societal costs belong in the main
      manuscript or supplement.
- [ ] Maintain causal-language and outcome-definition caveats during manuscript
      editing.
