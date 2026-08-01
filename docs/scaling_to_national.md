# Scaling from San Francisco to the U.S. national urban study

_Method/status updated 2026-07-30._

## Locked study design

- **Study universe:** 1,167 unique county GEOIDs in the exact county layer
  uploaded to Earth Engine.
- **Projection and exposure grid:** EPSG:5070, harmonized 90 m NDVI. Original
  30 m exports are aggregated with area averaging; original 90 m exports are
  aligned to the same 90 m grid origin.
- **Population:** WorldPop supplies within-county spatial weights; every county
  is rescaled to its exact ACS 2023 five-year age-18+ total.
- **Outcome:** CDC PLACES tract prevalence of adults ever told they have a
  depressive disorder. This is not strict current MDD.
- **Florida bridge:** the PLACES 2023 spatial release has null depression
  values for all Florida tracts. Missing Florida values only are filled from
  the immediately preceding official PLACES 2022 release on the same 2015
  tract geography. No other state or non-null value is replaced.
- **Effect:** Liu et al. (2023) pooled OR 0.931 (0.887–0.977), converted to RR
  at the locked national low-NDVI-quartile p0 = 0.191045. Primary RR =
  0.943436 (0.906571–0.981312).
- **Primary counterfactual:** uniform +0.05 NDVI at a 300 m exposure radius.
- **Valuation:** $21,280 societal cost per prevalent case (2024 USD), with
  $17,000–$23,000 sensitivity.

## Data gates completed

The national run is allowed only after these fail-closed gates pass:

1. Filename GEOIDs match the exact 1,167-county AOI.
2. The 56 out-of-AOI rasters are quarantined outside the active input folder.
3. All 1,167 active rasters are readable EPSG:5070 GeoTIFFs on aligned 90 m
   grids.
4. A full-pixel read finds valid NDVI within [-1, 1] and no unmasked `NaN` or
   infinite values.
5. ACS adult targets and county SVI cover all 1,167 GEOIDs uniquely.
6. National p0 processing succeeds for every county and reconciles allocated
   population to ACS targets.

The strengthened non-finite-value check matters. An initial harmonization
declared `-9999` as nodata while retaining internal `NaN` values in some files;
the InVEST convolution then returned non-finite results. Those preliminary
national totals were rejected, the rasters were rewritten with consistent
nodata encoding, and the full-read audit was rerun before modeling.

Final scenario QA also exposed a separate cap error: pixels whose baseline
NDVI already exceeded 0.90 were being lowered to 0.90. Scenario construction
now preserves those baseline pixels and caps proposed increases only. All SF
and national scenario/radius outputs were regenerated with this no-decrease
rule.

Machine-readable evidence:

- `results/summaries/national_ndvi_manifest.csv`
- `results/summaries/national_ndvi_audit.md`
- `results/summaries/national_p0_county_qa.csv`
- `results/summaries/national_final_qa.csv`

## Reproducible sequence

```bash
# 1. Quarantine files outside the locked AOI
python src/national/quarantine_unexpected_ndvi.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --ndvi-dir data/national/ndvi

# 2. Harmonize to aligned 90 m EPSG:5070 grids
python src/national/harmonize_ndvi_resolution.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --input-dir data/national/ndvi \
  --output-dir data/national/ndvi_90m --resolution 90

# 3. Full-read raster gate
python src/national/audit_ndvi_exports.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --ndvi-dir data/national/ndvi_90m \
  --expected-resolution 90 --full-read

# 4. Lock p0 and update config.yaml
python src/national/compute_national_p0.py \
  --prevalence <national_places_shapefile> \
  --population <national_worldpop_raster>

# 5. Primary national run; resumable and isolated by county
python src/national/run_national_batch.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --prevalence <national_places_shapefile> \
  --population <national_worldpop_raster> \
  --ndvi-dir data/national/ndvi_90m \
  --scenario uniform_005 --workers 8

# 6. Further scenarios/radii reuse the calibrated primary inputs
python src/national/run_national_batch.py <same shared arguments> \
  --scenario proportional_10pct --reuse-central-inputs

python src/national/run_national_batch.py <same shared arguments> \
  --scenario uniform_005 --search-radius 500 --reuse-central-inputs

# 7. Aggregate and validate
python src/national/aggregate_national.py --scenario uniform_005 --map
python src/national/summarize_national_scenarios.py
python src/national/national_equity.py
python src/national/summarize_radius_sensitivity.py
python src/national/qa_national_results.py
```

Each county has an isolated workspace and log. Completed counties are skipped
on restart unless `--force` is supplied.

## Interpretation and remaining refinements

- National benefit totals are prevalence-based modeled counterfactuals, not
  incidence reductions or randomized intervention forecasts.
- The 90 m exposure grid is a defensible common denominator for mixed original
  exports, but it cannot recover information lost in rasters originally
  exported at 90 m.
- County-level SVI describes between-county distribution; it masks
  within-county inequity and should complement tract-level city analyses.
- A flat national societal cost is appropriate for the primary analysis.
  Regional wage scaling remains a sensitivity because workplace productivity
  is the largest cost component.
- Alaska, Hawaii, and territories require projection and source-coverage
  decisions if added; the current AOI and EPSG:5070 workflow are CONUS-focused.

## Reproducibility gates

- Exact conda packages for the analysis platform are archived under
  `environment-locks/` and can be checked with
  `python src/reproducibility/export_environment_lock.py --check`.
- SHA-256 hashes for the active local inputs are archived in
  `reproducibility/input_checksums.csv` and can be recomputed with
  `python src/reproducibility/build_input_manifest.py --verify`.
- GitHub CI validates the committed NDVI manifest, all seven national summary
  tables, exact ACS adult-population reconciliation, finite/non-negative
  outputs, and the fail-closed final QA table.

## Remaining to-do

- Consider regional wage-adjusted costs and tract-level national SVI as
  manuscript extensions, not blockers for the present U.S. analysis.
