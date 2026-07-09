#!/usr/bin/env python3
"""
Build two InVEST inputs for San Francisco:
  1. sf_aoi.gpkg               - census-tract AOI, projected in meters
  2. baseline_prevalence.gpkg  - same tracts + a `risk_rate` field (depression)

SOURCES
  - Boundaries: US Census TIGER/Line 2024 census tracts (California, FIPS 06).
  - Prevalence: CDC PLACES census-tract 2024 release (Socrata `cwsq-ngmh`),
    measure DEPRESSION ("Depression among adults"). Data_Value is a percent,
    converted to a 0-1 ratio for the model's required `risk_rate` field.

REQUIREMENTS
    pip install geopandas requests pandas

USAGE
    python src/inputs/build_aoi_prevalence.py
    python src/inputs/build_aoi_prevalence.py --value-type "Age-adjusted prevalence"

NOTE
    Runs on your machine (needs internet). Not run in the Cowork sandbox.
    Set a CDC Socrata app token via env SOCRATA_APP_TOKEN to avoid throttling
    (optional for a single small query).
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
    sys.exit("Missing deps. Install: pip install geopandas requests pandas")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("build_aoi_prevalence")

# --- project paths (this file is <project>/src/inputs/) ---
BASE_DIR = Path(__file__).resolve().parents[2]
OUT_DIR = BASE_DIR / "data" / "urban-mental-health" / "inputs"

# --- constants ---
TRACTS_URL = "https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_06_tract.zip"  # CA=06
SF_COUNTYFP = "075"                       # San Francisco County
METRIC_CRS = "EPSG:26910"                 # NAD83 / UTM 10N (meters) — good for SF
PLACES_URL = "https://chronicdata.cdc.gov/resource/cwsq-ngmh.json"  # PLACES tract 2024
DEPRESSION = "DEPRESSION"                  # PLACES MeasureId


def load_sf_tracts() -> "gpd.GeoDataFrame":
    """Download CA tracts, keep San Francisco County, reproject to meters."""
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
    """Fetch SF depression prevalence from CDC PLACES; return GEOID + risk_rate."""
    params = {
        "stateabbr": "CA",
        "countyname": "San Francisco",
        "measureid": DEPRESSION,
        "$limit": "50000",
    }
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

    # Column names vary slightly by release: tract id is locationname or locationid.
    id_col = "locationname" if "locationname" in df else "locationid"
    df = df[df["data_value_type"] == value_type].copy()
    df["risk_rate"] = pd.to_numeric(df["data_value"], errors="coerce") / 100.0  # % -> ratio
    df = df.rename(columns={id_col: "GEOID"})[["GEOID", "risk_rate"]].dropna()
    LOGGER.info("Depression rows: %d (value_type=%s)", len(df), value_type)
    return df


def main():
    ap = argparse.ArgumentParser(description="Build SF AOI + depression prevalence inputs.")
    ap.add_argument("--value-type", default="Crude prevalence",
                    choices=["Crude prevalence", "Age-adjusted prevalence"],
                    help="PLACES Data_Value_Type to use (default: Crude prevalence).")
    cli = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tracts = load_sf_tracts()
    aoi_path = OUT_DIR / "sf_aoi.gpkg"
    tracts.to_file(aoi_path, driver="GPKG")
    LOGGER.info("Wrote AOI -> %s", aoi_path)

    dep = load_depression(cli.value_type)
    # Join prevalence onto tract geometries (GEOID is the 11-digit tract FIPS).
    prevalence = tracts.merge(dep, on="GEOID", how="left")
    missing = prevalence["risk_rate"].isna().sum()
    if missing:
        LOGGER.warning("%d tracts have no depression value (suppressed/short pop).", missing)
    prev_path = OUT_DIR / "baseline_prevalence.gpkg"
    prevalence.to_file(prev_path, driver="GPKG")
    LOGGER.info("Wrote prevalence (field 'risk_rate') -> %s", prev_path)
    LOGGER.info("These match run_model.py's aoi_path and baseline_prevalence_vector.")


if __name__ == "__main__":
    main()
