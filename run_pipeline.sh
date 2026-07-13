#!/usr/bin/env bash
# Run the full corrected SNAPP Urban Mental Health pipeline for SF, end to end.
#
# Prerequisites (once):
#   conda activate snapp
#   earthengine authenticate         # for the GEE NDVI step
#
# Usage:
#   bash run_pipeline.sh             # every step (rebuilds NDVI too)
#   bash run_pipeline.sh --skip-ndvi # reuse existing NDVI rasters (faster)
#   bash run_pipeline.sh --validate  # build inputs, validate the model, then stop
#   bash run_pipeline.sh --skip-ndvi --validate
#
# Stops at the first error (set -e). Applies every correction: cartographic AOI
# with water tracts dropped, mass-conserving adult population, data-driven p0
# (OR->RR), dual counterfactual, sensitivity, and the figure-rich summary.

set -euo pipefail
cd "$(dirname "$0")"        # repo root, regardless of where called

SKIP_NDVI=""
VALIDATE_ONLY=""
for a in "$@"; do
    case "$a" in
        --skip-ndvi) SKIP_NDVI=1 ;;
        --validate)  VALIDATE_ONLY="--validate" ;;
        *) echo "Unknown arg: $a  (use --skip-ndvi and/or --validate)"; exit 2 ;;
    esac
done

step() { echo; echo "==> $1"; }

if [ -z "$SKIP_NDVI" ]; then
    step "1/10  Baseline NDVI (GEE Landsat JJAS p90)"
    python src/inputs/ndvi/ndvi_gee.py
    step "2/12  Greening scenario rasters (reference, feasible, and ambitious)"
    python src/inputs/ndvi/make_ndvi_scenario.py
    python src/inputs/ndvi/make_ndvi_scenario.py --mode greenable \
        --output data/urban-mental-health/inputs/ndvi_scenario_greenable.tif
    python src/inputs/ndvi/make_ndvi_scenario.py --mode best_potential --percentile 95 \
        --output data/urban-mental-health/inputs/ndvi_scenario_bestpot.tif
    if [ -f data/urban-mental-health/raw/nlcd/nlcd_landcover.tif ]; then
        python src/inputs/ndvi/scenario_lulc_masked.py
    else
        echo "   LULC-masked scenario skipped (NLCD land-cover raster unavailable)."
    fi
    if [ -f data/urban-mental-health/raw/nlcd/nlcd_tcc.tif ]; then
        # SF-specific 30% canopy target from the checked-in TCC-to-NDVI fit.
        python src/inputs/ndvi/scenario_canopy_target.py --canopy-target 30 \
            --tcc-slope 0.01892 --tcc-intercept 0.07464
    else
        echo "   Canopy-target scenario skipped (NLCD canopy raster unavailable)."
    fi
else
    step "1-2/10  NDVI steps skipped (--skip-ndvi); reusing existing rasters"
fi

step "3/10  AOI + depression prevalence (cartographic cb_2024; drops water tracts)"
python src/inputs/build_aoi_prevalence.py --source api

step "3b  Verify AOI has a single clean layer (catches stale sf_aoi before modeling)"
python3 - <<'PY'
import sqlite3, sys
f = "data/urban-mental-health/inputs/aoi.gpkg"
layers = [r[0] for r in sqlite3.connect(f).execute("SELECT table_name FROM gpkg_contents")]
n = sqlite3.connect(f).execute(f"SELECT count(*) FROM '{layers[0]}'").fetchone()[0]
print(f"   AOI layers={layers}  tracts={n}")
if len(layers) != 1:
    sys.exit(f"ERROR: aoi.gpkg has {len(layers)} layers {layers} — a stale layer is present "
             "and the model may read the wrong one. Delete aoi.gpkg in Finder, then re-run.")
PY

step "4/10  Population (WorldPop US 100 m -> SF adults; mass-conserving)"
python src/inputs/fetch_population.py --adult-fraction 0.86

step "5/10  Health cost per case (societal, Greenberg pooled)"
python src/inputs/estimate_health_cost.py

step "6/10  Data-driven p0 (population-weighted PLACES prevalence -> refresh config RRs)"
python src/inputs/compute_p0.py

step "7/12  Model — marginal greening reference scenario"
python src/urban_mental_health/run_model.py ${VALIDATE_ONLY}

if [ -n "$VALIDATE_ONLY" ]; then
    echo; echo "==> Validate-only: inputs built and model validated. Stopping."
    exit 0
fi

step "8/12  Model — total value of existing greenness (NDVI=0 counterfactual)"
python src/urban_mental_health/run_model.py --total-greenness

step "9/12  Model — five alternative investment scenarios"
python src/urban_mental_health/run_scenarios.py

step "10/12  Sensitivity (effect_size x cost)"
python src/urban_mental_health/run_sensitivity.py

step "11/12  Summary + figures (maps, counterfactual bar, scenario comparison, sensitivity range, scatter)"
python src/urban_mental_health/summarize_results.py --map

step "10b  Equity analysis (concentration index vs neighborhood income; needs internet)"
python src/urban_mental_health/equity_analysis.py \
    || echo "   equity step skipped (ACS fetch failed?); rerun equity_analysis.py or pass --ses-file."

step "Sanity checks (population total + output-vs-AOI tract count)"
python3 - <<'PY'
import sqlite3, glob, sys
import rasterio, numpy as np
a = rasterio.open("data/urban-mental-health/inputs/population.tif").read(1, masked=True)
print("   pop sum = %.0f  (expect ~717k SF adults, not ~1.0M)" % np.nansum(a))
aoi = "data/urban-mental-health/inputs/aoi.gpkg"
al = [r[0] for r in sqlite3.connect(aoi).execute("SELECT table_name FROM gpkg_contents")][0]
na = sqlite3.connect(aoi).execute(f"SELECT count(*) FROM '{al}'").fetchone()[0]
g = sorted(glob.glob("data/urban-mental-health/runs/sf_baseline/output/*sum*.gpkg"))
if g:
    c = sqlite3.connect(g[0])
    t = [r[0] for r in c.execute("SELECT table_name FROM gpkg_contents")][0]
    no = c.execute(f"SELECT count(*) FROM '{t}'").fetchone()[0]
    print(f"   AOI tracts={na}  model-output tracts={no}")
    if no != na:
        sys.exit(f"ERROR: output tracts {no} != AOI {na} — model read a stale/other AOI layer.")
    print("   OK: model output matches the clean AOI.")
PY

echo; echo "==> Done. Results in results/summaries/ (results_summary.md, equity_summary.md)"
echo "    + results/figures/; model runs in data/urban-mental-health/runs/sf_baseline"
echo "    (+ sf_total_greenness). The best-potential scenario raster is built; compare"
echo "    scenarios with: python src/urban_mental_health/run_scenarios.py"
