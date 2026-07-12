#!/usr/bin/env python3
"""
Run the Urban Mental Health model for ONE US city (national-scale driver).

This is the per-city worker behind `run_national.sh`. It reuses the same data
sources as the SF pipeline but parameterized by a county GEOID, and writes
to a per-city workspace so cities can be processed independently / in parallel.

Key differences from the SF scripts (see docs/scaling_to_national.md):
  - AOI = one county polygon selected from a national counties-in-metro layer by GEOID.
  - CRS = EPSG:5070 (NAD83 / Conus Albers, meters) — valid across CONUS, unlike
    the SF-only UTM zone 10N used in the single-city scripts.
  - Prevalence tracts are selected by spatial intersection with the city.
  - Population is read with a windowed clip (clip_box) so the national raster is
    never loaded whole.
  - NDVI (ndvi_base) is expected to already exist per city (produced by the GEE
    city loop — your Code Editor script already iterates cities); ndvi_alt is
    generated here if not supplied.

INPUTS (national, shared across cities)
  --regions       national AOI polygon layer (counties in metros; field GEOID)
  --prevalence    national CDC PLACES tract shapefile (fields GEOID, DEPRESS)
  --population    national WorldPop US people-per-pixel raster
  --ndvi-dir      folder with per-city NDVI, file named <GEOID>_ndvi.tif
  --cost-file     inputs/health_cost_rate.txt (shared societal value)

REQUIREMENTS  (conda env `snapp`)
  geopandas, rioxarray, rasterio, natcap.invest

USAGE
  python src/national/run_city.py --geoid 0667000 \
      --regions data/national/counties.gpkg \
      --prevalence data/urban-mental-health/raw/cdc_places/prevalence_rate_usa_2021.shp \
      --population data/urban-mental-health/inputs/_worldpop/usa_pop_2024_CN_100m_R2025A_v1.tif \
      --ndvi-dir data/national/ndvi
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import geopandas as gpd
    import pandas as pd
    import rioxarray  # noqa: F401
    from rasterio.enums import Resampling
except ImportError:
    sys.exit("Missing deps. Install the `snapp` conda env (geopandas, rioxarray, rasterio).")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("run_city")

BASE_DIR = Path(__file__).resolve().parents[2]
NATIONAL_CRS = "EPSG:5070"          # NAD83 / Conus Albers (meters) — CONUS-wide
WORKSPACE_ROOT = BASE_DIR / "data" / "urban-mental-health" / "runs" / "national"

SEARCH_RADIUS_M = 300.0
SCENARIO_DELTA = 0.05               # uniform NDVI greening for ndvi_alt
SCENARIO_CAP = 0.90


def pick_geoid_col(gdf) -> str:
    for c in ("GEOID_PLAC", "GEOID", "PLACEFP", "GEOID20"):
        if c in gdf.columns:
            return c
    sys.exit(f"No GEOID column found in regions layer (have {list(gdf.columns)}).")


def build_city_inputs(cli, city_ws: Path) -> dict:
    """Build AOI, prevalence, population, ndvi_alt for one city; return model args."""
    inputs = city_ws / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    # --- 1. County AOI from the national counties-in-metro layer ---
    regions = gpd.read_file(cli.regions)
    gcol = pick_geoid_col(regions)
    city = regions[regions[gcol].astype(str) == cli.geoid]
    if city.empty:
        sys.exit(f"GEOID {cli.geoid} not found in {cli.regions}.")
    city = city.to_crs(NATIONAL_CRS)
    aoi_path = inputs / "aoi.gpkg"
    city[[gcol, "geometry"]].to_file(aoi_path, driver="GPKG")

    # --- 2. Prevalence: tracts intersecting the city, risk_rate = DEPRESS/100 ---
    tracts = gpd.read_file(cli.prevalence).to_crs(NATIONAL_CRS)
    hit = gpd.sjoin(tracts, city[["geometry"]], predicate="intersects", how="inner")
    hit = hit.drop(columns=[c for c in hit.columns if c.startswith("index_")])
    hit["risk_rate"] = pd.to_numeric(hit["DEPRESS"], errors="coerce") / 100.0
    prev_path = inputs / "baseline_prevalence.gpkg"
    hit[["GEOID", "risk_rate", "geometry"]].to_file(prev_path, driver="GPKG")

    # --- 3. Population: windowed clip to the city, reproject to meters ---
    pop = rioxarray.open_rasterio(cli.population, masked=True)
    city_in_pop = city.to_crs(pop.rio.crs)
    minx, miny, maxx, maxy = city_in_pop.total_bounds
    pop_win = pop.rio.clip_box(minx, miny, maxx, maxy)
    pop_clip = pop_win.rio.clip(city_in_pop.geometry, city_in_pop.crs, drop=True)
    pop_proj = pop_clip.rio.reproject(NATIONAL_CRS, resampling=Resampling.bilinear)
    pop_proj.rio.write_nodata(float("nan"), inplace=True)
    pop_proj.attrs.pop("_FillValue", None)          # avoid xarray _FillValue clash
    pop_path = inputs / "population.tif"
    pop_proj.rio.to_raster(pop_path, driver="GTiff", compress="LZW")

    # --- 4. NDVI: baseline from the per-city GEE export; scenario derived here ---
    ndvi_base = cli.ndvi_dir / f"{cli.geoid}_ndvi.tif"
    if not ndvi_base.exists():
        sys.exit(f"NDVI not found for {cli.geoid}: {ndvi_base}. Run the GEE city loop first.")
    base = rioxarray.open_rasterio(ndvi_base, masked=True).squeeze()
    alt = (base + SCENARIO_DELTA).clip(max=SCENARIO_CAP).where(~base.isnull())
    alt = alt.rio.write_crs(base.rio.crs)
    alt.rio.write_nodata(float("nan"), inplace=True)
    alt.attrs.pop("_FillValue", None)
    ndvi_alt = inputs / "ndvi_alt.tif"
    alt.rio.to_raster(ndvi_alt, driver="GTiff", compress="LZW")

    args = {
        "workspace_dir": str(city_ws),
        "results_suffix": cli.geoid,
        "aoi_path": str(aoi_path),
        "population_raster": str(pop_path),
        "search_radius": SEARCH_RADIUS_M,
        "effect_size": 0.93,
        "baseline_prevalence_vector": str(prev_path),
        "model_option": "ndvi",
        "ndvi_base": str(ndvi_base),
        "ndvi_alt": str(ndvi_alt),
    }
    if cli.cost_file.exists():
        args["health_cost_rate"] = float(cli.cost_file.read_text().strip())
    return args


def main():
    ap = argparse.ArgumentParser(description="Run Urban Mental Health model for one city.")
    ap.add_argument("--geoid", required=True, help="County GEOID, 5-digit FIPS (e.g. 06075).")
    ap.add_argument("--regions", type=Path, required=True, help="National AOI layer (counties in metros).")
    ap.add_argument("--prevalence", type=Path,
                    default=BASE_DIR / "data/urban-mental-health/raw/cdc_places/prevalence_rate_usa_2021.shp")
    ap.add_argument("--population", type=Path, required=True, help="National WorldPop raster.")
    ap.add_argument("--ndvi-dir", type=Path, required=True, help="Folder of <GEOID>_ndvi.tif.")
    ap.add_argument("--cost-file", type=Path,
                    default=BASE_DIR / "data/urban-mental-health/inputs/health_cost_rate.txt")
    cli = ap.parse_args()

    city_ws = WORKSPACE_ROOT / cli.geoid
    city_ws.mkdir(parents=True, exist_ok=True)
    LOGGER.info("[%s] building inputs...", cli.geoid)
    args = build_city_inputs(cli, city_ws)

    from natcap.invest import urban_mental_health as model
    warnings = model.validate(args)
    if warnings:
        for keys, msg in warnings:
            LOGGER.warning("[%s] validate: %s: %s", cli.geoid, keys, msg)
    LOGGER.info("[%s] running model -> %s", cli.geoid, city_ws)
    model.execute(args)
    LOGGER.info("[%s] done.", cli.geoid)


if __name__ == "__main__":
    main()
