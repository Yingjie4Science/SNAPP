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
# RISK RATIO per +0.1 NDVI. Converted OR->RR from Liu et al. 2023 (OR 0.931) at
# p0=0.20; matches config.yaml effect_size. See docs/effect_size.md.
EFFECT_SIZE_RR = 0.944
SCENARIO_DELTA = 0.05               # uniform NDVI greening for ndvi_alt
SCENARIO_CAP = 0.90


# State FIPS -> US Census region, for optional per-region cost (regional_cost.py).
FIPS_REGION = {}
for _reg, _fips in {
    "Northeast": "09 23 25 33 44 50 34 36 42",
    "Midwest": "18 17 26 39 55 19 20 27 29 31 38 46",
    "South": "10 11 12 13 24 37 45 51 54 01 21 28 47 05 22 40 48",
    "West": "04 08 16 30 32 35 49 56 02 06 15 41 53",
}.items():
    for _f in _fips.split():
        FIPS_REGION[_f] = _reg


def resolve_cost(cli) -> float | None:
    """Per-region societal cost from config/cost_by_region.csv if available, else flat file.

    Maps the county's state FIPS -> Census region -> cost_rate_usd. Falls back to
    the single --cost-file value when the region table is missing or unmatched.
    """
    import csv
    f = getattr(cli, "cost_by_region", None)
    if f and f.exists():
        region = FIPS_REGION.get(cli.geoid[:2])
        if region:
            with open(f) as fh:
                for r in csv.DictReader(fh):
                    if (r.get("region") or "").strip() == region:
                        val = float(r["cost_rate_usd"])
                        LOGGER.info("[%s] cost $%.0f (region=%s).", cli.geoid, val, region)
                        return val
    if cli.cost_file.exists():
        return float(cli.cost_file.read_text().strip())
    return None


def resolve_adult_fraction(cli) -> float:
    """Per-county 18+ share from the ACS lookup if present, else the flat default.

    config/adult_fraction.csv (from fetch_adult_fraction.py) maps GEOID ->
    adult_fraction. If the file exists and lists this county, use it; otherwise
    fall back to --adult-fraction (0.86).
    """
    import csv
    f = cli.adult_fraction_file
    if f and f.exists():
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if (r.get("GEOID") or "").strip() == cli.geoid:
                    val = float(r["adult_fraction"])
                    LOGGER.info("[%s] adult_fraction %.4f (per-county, ACS).", cli.geoid, val)
                    return val
        LOGGER.info("[%s] not in %s; using flat %.3f.", cli.geoid, f.name, cli.adult_fraction)
    return cli.adult_fraction


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
    # Reproject people-per-pixel counts, then rescale to preserve the clipped total
    # (bilinear reprojection across CRS/resolution is NOT count-preserving; it
    # inflated SF ~15%). Mass conservation before adult scaling.
    pre_sum = float(pop_clip.sum(skipna=True))
    pop_proj = pop_clip.rio.reproject(NATIONAL_CRS, resampling=Resampling.bilinear)
    post_sum = float(pop_proj.sum(skipna=True))
    if post_sum > 0 and pre_sum > 0:
        pop_proj = (pop_proj * (pre_sum / post_sum)).rio.write_crs(NATIONAL_CRS)
    frac = resolve_adult_fraction(cli)              # CDC PLACES prevalence is ADULT (18+);
    if frac != 1.0:                                  # scale all-ages WorldPop to adults so
        crs = pop_proj.rio.crs                        # cases aren't ~20% high
        pop_proj = (pop_proj * frac).rio.write_crs(crs)
    pop_proj.rio.write_nodata(float("nan"), inplace=True)
    pop_proj.attrs.pop("_FillValue", None)          # avoid xarray _FillValue clash
    pop_path = inputs / "population.tif"
    pop_proj.rio.to_raster(pop_path, driver="GTiff", compress="LZW")

    # --- 4. NDVI: baseline from the per-city GEE export; scenario derived here ---
    ndvi_base = cli.ndvi_dir / f"{cli.geoid}_ndvi.tif"
    if not ndvi_base.exists():
        sys.exit(f"NDVI not found for {cli.geoid}: {ndvi_base}. Run the GEE city loop first.")
    base = rioxarray.open_rasterio(ndvi_base, masked=True).squeeze()
    if getattr(cli, "total_greenness", False):
        # Value EXISTING greenness: baseline = NDVI 0 (bare), alt = current NDVI.
        zero = (base * 0.0).rio.write_crs(base.rio.crs)
        zero.rio.write_nodata(float("nan"), inplace=True)
        zero.attrs.pop("_FillValue", None)
        model_base = inputs / "ndvi_zero.tif"
        zero.rio.to_raster(model_base, driver="GTiff", compress="LZW")
        model_alt = ndvi_base                        # today's greenness is the "improved" state
    else:
        # Marginal greening scenario: base = current NDVI, alt = current + delta.
        alt = (base + SCENARIO_DELTA).clip(max=SCENARIO_CAP).where(~base.isnull())
        alt = alt.rio.write_crs(base.rio.crs)
        alt.rio.write_nodata(float("nan"), inplace=True)
        alt.attrs.pop("_FillValue", None)
        model_alt = inputs / "ndvi_alt.tif"
        alt.rio.to_raster(model_alt, driver="GTiff", compress="LZW")
        model_base = ndvi_base

    args = {
        "workspace_dir": str(city_ws),
        "results_suffix": cli.geoid,
        "aoi_path": str(aoi_path),
        "population_raster": str(pop_path),
        "search_radius": SEARCH_RADIUS_M,
        "effect_size": EFFECT_SIZE_RR,
        "baseline_prevalence_vector": str(prev_path),
        "model_option": "ndvi",
        "ndvi_base": str(model_base),
        "ndvi_alt": str(model_alt),
    }
    cost = resolve_cost(cli)
    if cost is not None:
        args["health_cost_rate"] = cost
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
    ap.add_argument("--adult-fraction", type=float, default=0.86,
                    help="Fallback all-ages->adult (18+) scale for counties not in the "
                         "lookup file, since CDC PLACES prevalence is adult. Default 0.86 "
                         "(US 18+), matching the corrected SF run. Use 1.0 to disable.")
    ap.add_argument("--adult-fraction-file", type=Path,
                    default=BASE_DIR / "config" / "adult_fraction.csv",
                    help="Per-county 18+ share lookup (GEOID,adult_fraction) from "
                         "fetch_adult_fraction.py. Used when present; overrides the flat "
                         "value per county. Missing counties fall back to --adult-fraction.")
    ap.add_argument("--cost-by-region", type=Path,
                    default=BASE_DIR / "config" / "cost_by_region.csv",
                    help="Per-region societal cost table (from regional_cost.py). Used when "
                         "present: maps county state -> Census region -> cost. Falls back to "
                         "--cost-file otherwise.")
    ap.add_argument("--total-greenness", action="store_true",
                    help="Value EXISTING greenness (baseline NDVI=0 vs current) instead of "
                         "the marginal greening scenario. Writes to a separate runs root.")
    cli = ap.parse_args()

    ws_root = (WORKSPACE_ROOT.parent / "national_total_greenness"
               if cli.total_greenness else WORKSPACE_ROOT)
    city_ws = ws_root / cli.geoid
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
