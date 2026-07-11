#!/usr/bin/env bash
# National multi-city run: loop config/cities.csv and run the model per city.
#
# Prereqs:
#   conda activate snapp
#   - a national "places" polygon layer (--places)
#   - the national WorldPop raster (already in inputs/_worldpop/)
#   - per-city NDVI rasters named <GEOID>_ndvi.tif in --ndvi-dir
#     (produce these with the GEE city loop; see src/sf_ndvi/ndvi_gee.py and
#      docs/scaling_to_national.md)
#   - a societal cost value: python src/inputs/estimate_health_cost.py
#
# Usage:
#   bash run_national.sh PLACES_LAYER NDVI_DIR
# Example:
#   bash run_national.sh data/national/places.gpkg data/national/ndvi

set -euo pipefail
cd "$(dirname "$0")"

PLACES="${1:?path to national places layer required}"
NDVI_DIR="${2:?path to per-city NDVI dir required}"
POP="data/urban-mental-health/inputs/_worldpop/usa_pop_2024_CN_100m_R2025A_v1.tif"
CITIES="config/cities.csv"

# Ensure the shared societal cost value exists.
[ -f data/urban-mental-health/inputs/health_cost_rate.txt ] || \
    python src/inputs/estimate_health_cost.py

# Loop cities (skip header and comment lines), run each independently.
tail -n +2 "$CITIES" | grep -v '^#' | while IFS=, read -r geoid name; do
    [ -z "$geoid" ] && continue
    echo "==> $geoid  $name"
    python src/national/run_city.py \
        --geoid "$geoid" \
        --places "$PLACES" \
        --population "$POP" \
        --ndvi-dir "$NDVI_DIR" \
        || echo "    WARNING: $geoid failed; continuing."
done

echo "==> National run complete. Per-city outputs in data/urban-mental-health/workspace_national/<GEOID>/"
