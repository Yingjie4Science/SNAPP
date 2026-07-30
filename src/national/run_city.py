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
    import numpy as np
    import pandas as pd
    import rioxarray  # noqa: F401
    import xarray as xr
    from rasterio.enums import Resampling
except ImportError:
    sys.exit("Missing deps. Install the `snapp` conda env (geopandas, rioxarray, rasterio).")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("run_city")

BASE_DIR = Path(__file__).resolve().parents[2]
NATIONAL_CRS = "EPSG:5070"          # NAD83 / Conus Albers (meters) — CONUS-wide
WORKSPACE_ROOT = BASE_DIR / "data" / "urban-mental-health" / "runs" / "national"

try:
    import yaml
    _MODEL = (yaml.safe_load((BASE_DIR / "config.yaml").read_text()) or {}).get("model", {})
except Exception as exc:
    sys.exit(f"Could not read model settings from config.yaml: {exc}")

SEARCH_RADIUS_M = float(_MODEL.get("search_radius_m", 300.0))
# RISK RATIO per +0.1 NDVI, converted from the Liu et al. pooled OR at the
# documented p0. Reading config prevents national runs from silently retaining
# an obsolete hard-coded conversion after p0 is finalized.
EFFECT_SIZE_RR = float(_MODEL.get("effect_size", 0.944))
SCENARIO_DELTA = 0.05
SCENARIO_CAP = 0.90
SCENARIO_TARGET = 0.60
SCENARIO_PERCENT = 10.0
SCENARIO_PERCENTILE = 95.0


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


def resolve_adult_population(cli) -> tuple[float, float | None]:
    """Return per-county adult fraction and, when available, ACS adult total.

    config/adult_population.csv maps GEOID -> adult_fraction and
    population_adult. The adult total calibrates WorldPop's aggregate while
    retaining its spatial pattern. A legacy fraction-only file is supported.
    """
    import csv
    f = cli.adult_fraction_file
    if f and f.exists():
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if (r.get("GEOID") or "").strip() == cli.geoid:
                    val = float(r["adult_fraction"])
                    target = (float(r["population_adult"])
                              if r.get("population_adult") not in (None, "") else None)
                    LOGGER.info("[%s] adult_fraction %.4f; target=%s (ACS).",
                                cli.geoid, val, target)
                    return val, target
        LOGGER.info("[%s] not in %s; using flat %.3f.", cli.geoid, f.name, cli.adult_fraction)
    return cli.adult_fraction, None


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
    # Read only the requested county's tracts. Loading the full national layer
    # 1,167 times made the national loop needlessly slow. GEOID prefixes are
    # exact county identifiers for census tracts, so no spatial join is needed.
    try:
        hit = gpd.read_file(
            cli.prevalence, where=f"GEOID LIKE '{cli.geoid}%'"
        )
    except Exception:
        tracts = gpd.read_file(cli.prevalence)
        hit = tracts[tracts["GEOID"].astype(str).str.startswith(cli.geoid)].copy()
    hit = hit.to_crs(NATIONAL_CRS)
    if hit.empty:
        sys.exit(f"[{cli.geoid}] no PLACES tracts found.")
    hit["risk_rate"] = pd.to_numeric(hit["DEPRESS"], errors="coerce") / 100.0
    hit["risk_source"] = "places_2023_brfss_2021"
    if cli.geoid.startswith("12") and cli.florida_places_bridge.exists():
        bridge = pd.read_csv(
            cli.florida_places_bridge, dtype={"tractfips": str}
        )
        bridge["tractfips"] = bridge["tractfips"].str.zfill(11)
        bridge_values = dict(
            zip(
                bridge["tractfips"],
                pd.to_numeric(bridge["depression_crudeprev"], errors="coerce")
                / 100.0,
            )
        )
        missing = hit["risk_rate"].isna()
        hit.loc[missing, "risk_rate"] = (
            hit.loc[missing, "GEOID"].astype(str).str.zfill(11).map(bridge_values)
        )
        matched = missing & hit["risk_rate"].notna()
        hit.loc[matched, "risk_source"] = "places_2022_florida_bridge"
        LOGGER.info(
            "[%s] Florida PLACES bridge matched %d/%d null tracts.",
            cli.geoid,
            int(matched.sum()),
            int(missing.sum()),
        )
    hit = hit[hit["risk_rate"].between(0, 1, inclusive="both")].copy()
    if hit.empty:
        sys.exit(f"[{cli.geoid}] no non-null PLACES depression estimates.")
    prev_path = inputs / "baseline_prevalence.gpkg"
    hit[["GEOID", "risk_rate", "risk_source", "geometry"]].to_file(
        prev_path, driver="GPKG"
    )

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
    frac, target_adult = resolve_adult_population(cli)  # PLACES prevalence is adult;
    if frac != 1.0:                                  # scale all-ages WorldPop to adults so
        crs = pop_proj.rio.crs                        # cases aren't ~20% high
        pop_proj = (pop_proj * frac).rio.write_crs(crs)
    if target_adult is not None:
        current = float(pop_proj.sum(skipna=True))
        if current <= 0:
            sys.exit(f"[{cli.geoid}] adult population raster sums to zero.")
        crs = pop_proj.rio.crs
        pop_proj = (pop_proj * (target_adult / current)).rio.write_crs(crs)
        LOGGER.info("[%s] calibrated WorldPop adult sum %.0f -> %.0f.",
                    cli.geoid, current, target_adult)
    pop_proj.rio.write_nodata(float("nan"), inplace=True)
    pop_proj.attrs.pop("_FillValue", None)          # avoid xarray _FillValue clash
    pop_path = inputs / "population.tif"
    pop_proj.rio.to_raster(pop_path, driver="GTiff", compress="LZW")
    # Record adult population so the aggregator can report a per-1,000-adult rate.
    (city_ws / "adult_pop.txt").write_text(f"{float(pop_proj.sum(skipna=True)):.0f}\n")

    # --- 4. NDVI: baseline from the per-city GEE export; scenario derived here ---
    ndvi_base = cli.ndvi_dir / f"{cli.geoid}_ndvi.tif"
    if not ndvi_base.exists():
        sys.exit(f"NDVI not found for {cli.geoid}: {ndvi_base}. Run the GEE city loop first.")
    base = rioxarray.open_rasterio(ndvi_base, masked=True).squeeze()
    if cli.scenario == "existing_greenness":
        # Value EXISTING greenness: baseline = NDVI 0 (bare), alt = current NDVI.
        zero = (base * 0.0).rio.write_crs(base.rio.crs)
        zero.rio.write_nodata(float("nan"), inplace=True)
        zero.attrs.pop("_FillValue", None)
        model_base = inputs / "ndvi_zero.tif"
        zero.rio.to_raster(model_base, driver="GTiff", compress="LZW")
        model_alt = ndvi_base                        # today's greenness is the "improved" state
    else:
        if cli.scenario == "uniform_005":
            alt = base + SCENARIO_DELTA
        elif cli.scenario == "proportional_10pct":
            alt = base * (1.0 + SCENARIO_PERCENT / 100.0)
        elif cli.scenario == "greenable_005":
            alt = base + xr.where(base < SCENARIO_TARGET, SCENARIO_DELTA, 0.0)
        elif cli.scenario == "best_potential_p95":
            p95 = float(np.nanpercentile(base.values, SCENARIO_PERCENTILE))
            alt = xr.where(base < p95, p95, base)
            LOGGER.info("[%s] within-county p95 NDVI=%.4f.", cli.geoid, p95)
        else:
            raise ValueError(f"Unsupported scenario: {cli.scenario}")
        alt = xr.where(
            base > SCENARIO_CAP, base, alt.clip(max=SCENARIO_CAP)
        ).where(~base.isnull())
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
        "search_radius": float(cli.search_radius),
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
    ap.add_argument(
        "--florida-places-bridge",
        type=Path,
        default=BASE_DIR / "config" / "places_florida_2022.csv",
        help="Official PLACES 2022 tract values used only where PLACES 2023 is "
        "null in Florida.",
    )
    ap.add_argument("--cost-file", type=Path,
                    default=BASE_DIR / "data/urban-mental-health/inputs/health_cost_rate.txt")
    ap.add_argument("--adult-fraction", type=float, default=0.86,
                    help="Fallback all-ages->adult (18+) scale for counties not in the "
                         "lookup file, since CDC PLACES prevalence is adult. Default 0.86 "
                         "(US 18+), matching the corrected SF run. Use 1.0 to disable.")
    ap.add_argument("--adult-fraction-file", type=Path,
                    default=BASE_DIR / "config" / "adult_population.csv",
                    help="Per-county ACS lookup (GEOID,adult_fraction,population_adult). "
                         "Used when present; missing counties fall back to "
                         "--adult-fraction without aggregate calibration.")
    ap.add_argument("--cost-by-region", type=Path,
                    default=BASE_DIR / "config" / "cost_by_region.csv",
                    help="Per-region societal cost table (from regional_cost.py). Used when "
                         "present: maps county state -> Census region -> cost. Falls back to "
                         "--cost-file otherwise.")
    ap.add_argument(
        "--scenario",
        choices=[
            "uniform_005",
            "proportional_10pct",
            "greenable_005",
            "best_potential_p95",
            "existing_greenness",
        ],
        default="uniform_005",
        help="National greening counterfactual. The default is uniform +0.05 NDVI.",
    )
    ap.add_argument(
        "--search-radius",
        type=float,
        default=SEARCH_RADIUS_M,
        help="Residential exposure radius in metres.",
    )
    ap.add_argument(
        "--total-greenness",
        action="store_true",
        help="Deprecated alias for --scenario existing_greenness.",
    )
    cli = ap.parse_args()

    if cli.total_greenness:
        cli.scenario = "existing_greenness"
    scenario_root = (
        "national" if cli.scenario == "uniform_005"
        else f"national_{cli.scenario}"
    )
    if float(cli.search_radius) != SEARCH_RADIUS_M:
        scenario_root += f"_radius_{int(cli.search_radius)}m"
    ws_root = WORKSPACE_ROOT.parent / scenario_root
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
