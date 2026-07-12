#!/usr/bin/env bash
# National multi-city run: loop config/regions.csv (counties in metros) and run
# the model per county.
#
# Prereqs (conda activate snapp):
#   - counties-in-metro AOI layer  (build_metro_counties.py -> data/national/counties.gpkg)
#   - config/regions.csv           (county GEOID list; also written by build_metro_counties.py)
#   - national WorldPop raster      (in data/urban-mental-health/inputs/_worldpop/)
#   - per-county NDVI rasters named <GEOID>_ndvi.tif in --ndvi-dir (GEE loop)
#   - a societal cost value:        python src/inputs/estimate_health_cost.py
#
# Usage:
#   bash run_national.sh COUNTIES_LAYER NDVI_DIR
# Example:
#   bash run_national.sh data/national/counties.gpkg data/national/ndvi

set -euo pipefail
cd "$(dirname "$0")"

REGIONS="${1:?path to counties-in-metro layer required}"
NDVI_DIR="${2:?path to per-county NDVI dir required}"
POP="data/urban-mental-health/inputs/_worldpop/usa_pop_2024_CN_100m_R2025A_v1.tif"
REGIONS_CSV="config/regions.csv"

# Ensure the shared societal cost value exists.
[ -f data/urban-mental-health/inputs/health_cost_rate.txt ] || \
    python src/inputs/estimate_health_cost.py

# Loop counties (skip header + comment lines); each runs independently.
tail -n +2 "$REGIONS_CSV" | grep -v '^#' | while IFS=, read -r geoid name; do
    [ -z "$geoid" ] && continue
    echo "==> $geoid  $name"
    python src/national/run_city.py \
        --geoid "$geoid" \
        --regions "$REGIONS" \
        --population "$POP" \
        --ndvi-dir "$NDVI_DIR" \
        || echo "    WARNING: $geoid failed; continuing."
done

echo "==> National run complete. Per-county outputs in data/urban-mental-health/runs/national/<GEOID>/"
