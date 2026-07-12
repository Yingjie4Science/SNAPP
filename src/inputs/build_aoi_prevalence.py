#!/usr/bin/env python3
"""
Build two InVEST inputs for San Francisco:
  1. aoi.gpkg               - census-tract AOI, projected in meters
  2. baseline_prevalence.gpkg  - same tracts + a `risk_rate` field (depression)

TWO PREVALENCE SOURCES (choose with --source):
  local  (default) Your CDC PLACES shapefile at
         data/urban-mental-health/raw/cdc_places/prevalence_rate_usa_2021.shp
         (fields include GEOID + DEPRESS = crude % prevalence, 2021). Offline.
  api    US Census cartographic tracts (cb_2024, per project convention — see
         docs/data_boundaries.md) + CDC PLACES 2024 release pulled live from
         Socrata (dataset cwsq-ngmh, measure DEPRESSION). Needs internet.

In both cases DEPRESS/Data_Value (a percent) becomes `risk_rate` (a 0-1 ratio),
and outputs are projected to EPSG:26910 (meters) — the filenames run_model.py
expects.

REQUIREMENTS
    conda env: geopandas, pandas, requests   (already in environment.yml)

USAGE
    python src/inputs/build_aoi_prevalence.py                     # local shapefile
    python src/inputs/build_aoi_prevalence.py --source api        # live CDC/Census
    python src/inputs/build_aoi_prevalence.py --source api --value-type "Age-adjusted prevalence"
"""

import argparse
import io
import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge geopandas pandas requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("build_aoi_prevalence")

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_DIR = BASE_DIR / "data" / "urban-mental-health" / "inputs"
DEFAULT_SHP = (BASE_DIR / "data" / "urban-mental-health" / "raw" / "cdc_places"
               / "prevalence_rate_usa_2021.shp")

METRIC_CRS = "EPSG:26910"          # NAD83 / UTM 10N (meters) — good for SF
SF_COUNTY_FIPS = "06075"           # state 06 (CA) + county 075 (San Francisco)
SF_COUNTYFP = "075"                # county-only code (TIGER field COUNTYFP)

# --- api route sources (cartographic boundary files; see docs/data_boundaries.md) ---
TRACTS_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_tract_500k.zip"
PLACES_URL = "https://chronicdata.cdc.gov/resource/cwsq-ngmh.json"
DEPRESSION = "DEPRESSION"


# --------------------------------------------------------------------------
# Local source: the CDC PLACES prevalence shapefile
# --------------------------------------------------------------------------
def build_local(shp: Path):
    """Return (aoi, prevalence) GeoDataFrames for SF from the local shapefile."""
    if not shp.exists():
        sys.exit(f"Shapefile not found: {shp}\nUse --source api, or check the path.")
    LOGGER.info("Reading local prevalence shapefile: %s", shp.name)
    gdf = gpd.read_file(shp)
    sf = gdf[gdf["GEOID"].astype(str).str.startswith(SF_COUNTY_FIPS)].copy()
    if sf.empty:
        sys.exit("No SF tracts (GEOID starting 06075) found in the shapefile.")
    LOGGER.info("San Francisco tracts: %d", len(sf))
    sf["risk_rate"] = pd.to_numeric(sf["DEPRESS"], errors="coerce") / 100.0  # % -> ratio
    sf = sf.to_crs(METRIC_CRS)
    aoi = sf[["GEOID", "geometry"]]
    prevalence = sf[["GEOID", "risk_rate", "geometry"]]
    return aoi, prevalence


# --------------------------------------------------------------------------
# API route: TIGER tracts + CDC PLACES Socrata
# --------------------------------------------------------------------------
def load_sf_tracts():
    LOGGER.info("Downloading Census tracts: %s", TRACTS_URL)
    r = requests.get(TRACTS_URL, timeout=300)
    r.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(tmp)
        shp = next(Path(tmp).glob("*.shp"))
        tracts = gpd.read_file(shp)
    sf = tracts[tracts["COUNTYFP"] == SF_COUNTYFP].copy()
    LOGGER.info("San Francisco tracts: %d", len(sf))
    return sf.to_crs(METRIC_CRS)[["GEOID", "geometry"]]


def load_depression(value_type: str) -> "pd.DataFrame":
    params = {"stateabbr": "CA", "countyname": "San Francisco",
              "measureid": DEPRESSION, "$limit": "50000"}
    headers = {}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    LOGGER.info("Querying CDC PLACES (%s, %s)", DEPRESSION, value_type)
    r = requests.get(PLACES_URL, params=params, headers=headers, timeout=120)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        sys.exit("PLACES returned no rows — check the dataset id / filters.")
    id_col = "locationname" if "locationname" in df else "locationid"
    df = df[df["data_value_type"] == value_type].copy()
    df["risk_rate"] = pd.to_numeric(df["data_value"], errors="coerce") / 100.0
    return df.rename(columns={id_col: "GEOID"})[["GEOID", "risk_rate"]].dropna()


def build_api(value_type: str):
    tracts = load_sf_tracts()
    dep = load_depression(value_type)
    prevalence = tracts.merge(dep, on="GEOID", how="left")
    missing = prevalence["risk_rate"].isna().sum()
    if missing:
        LOGGER.warning("%d tracts have no depression value (suppressed/short pop).", missing)
    return tracts, prevalence


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build SF AOI + depression prevalence inputs.")
    ap.add_argument("--source", choices=["local", "api"], default="local",
                    help="local shapefile (default) or live CDC/Census API.")
    ap.add_argument("--prevalence-shp", type=Path, default=DEFAULT_SHP,
                    help="Path to the local CDC prevalence shapefile.")
    ap.add_argument("--value-type", default="Crude prevalence",
                    choices=["Crude prevalence", "Age-adjusted prevalence"],
                    help="PLACES Data_Value_Type (api source only).")
    cli = ap.parse_args()

    if cli.source == "local":
        aoi, prevalence = build_local(cli.prevalence_shp)
    else:
        aoi, prevalence = build_api(cli.value_type)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    aoi_path = OUT_DIR / "aoi.gpkg"
    prev_path = OUT_DIR / "baseline_prevalence.gpkg"
    aoi.to_file(aoi_path, driver="GPKG")
    prevalence.to_file(prev_path, driver="GPKG")
    LOGGER.info("Wrote AOI -> %s", aoi_path)
    LOGGER.info("Wrote prevalence (field 'risk_rate') -> %s", prev_path)
    LOGGER.info("These match run_model.py's aoi_path and baseline_prevalence_vector.")


if __name__ == "__main__":
    main()
