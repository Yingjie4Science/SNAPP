#!/usr/bin/env bash
# Run the full SNAPP Urban Mental Health pipeline end to end.
#
# Prerequisites (once):
#   conda activate snapp
#   earthengine authenticate        # for the GEE NDVI step
#
# Usage:
#   bash run_pipeline.sh            # run every step
#   bash run_pipeline.sh --validate # build inputs, then only validate the model
#
# Stops at the first error (set -e). Steps are ordered so each one's inputs
# exist before it runs. Comment out a step if you've already produced its output.

set -euo pipefail
cd "$(dirname "$0")"        # run from the repo root regardless of where called

VALIDATE_ONLY=""
[ "${1:-}" = "--validate" ] && VALIDATE_ONLY="--validate"

echo "==> 1/6  Baseline NDVI (GEE Landsat p90)"
python src/sf_ndvi/ndvi_gee.py

echo "==> 2/6  Greening scenario (ndvi_alt)"
python src/inputs/make_ndvi_scenario.py

echo "==> 3/6  AOI + depression prevalence (local CDC shapefile)"
python src/inputs/build_aoi_prevalence.py

echo "==> 4/6  Population raster (WorldPop US 100 m -> SF, adults only)"
python src/inputs/fetch_population.py --adult-fraction 0.86   # SF adult (>=18) share

echo "==> 5/6  Health cost per case (societal, Greenberg 2021)"
python src/inputs/estimate_health_cost.py

echo "==> 6/6  Urban Mental Health model"
python src/urban_mental_health/run_model.py ${VALIDATE_ONLY}

echo "==> Done. Model outputs are in data/urban-mental-health/workspace/"
