#!/usr/bin/env python3
"""
Build the national AOI layer: US COUNTIES that fall within or overlap a
Metropolitan area (Metro / metdiv). County-based adaptation of
00b1-aoi-places-in-metro.ipynb (which used *places*); per project decision the
study unit here is the county intersecting a metro.

METHOD (mirrors the notebook, counties instead of places)
    - Load a metro layer and a county layer.
    - sjoin(counties, metros, how='inner', predicate='intersects')  -> counties
      touching/overlapping a metro; drop_duplicates on county GEOID.
    - Exclude non-mainland STATEFP ['02','15','60','66','69','72','78'] (AK, HI,
      PR, GU, VI, AS, MP); optionally drop DC ('11').
    - Write data/national/counties.gpkg + config/regions.csv (GEOID list that
      run_national.sh loops).

LAYERS
    --metro-layer  : your metro shapefile (e.g. the notebook's
        data/aoi/cb_2020_us_metro_combined_metdiv_no_overlap.shp) for an exact
        match. If omitted, TIGER CBSA is downloaded and filtered to Metropolitan
        Statistical Areas (LSAD == 'M1').
    --county-layer : a county polygon layer; if omitted, TIGER counties download.
    Metro id/name columns are auto-detected (GEOID_METR/NAME_METRO or CBSAFP/NAME).

REQUIREMENTS  (conda env `snapp`): geopandas, pandas, requests
USAGE
    python src/national/build_metro_counties.py \
        --metro-layer data/aoi/cb_2020_us_metro_combined_metdiv_no_overlap.shp
    python src/national/build_metro_counties.py           # TIGER CBSA fallback
"""

import argparse
import csv
import io
import logging
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

try:
    import geopandas as gpd
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge geopandas pandas requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("build_metro_counties")

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_GPKG = BASE_DIR / "data" / "national" / "counties.gpkg"
REGIONS_CSV = BASE_DIR / "config" / "regions.csv"
TIGER = "https://www2.census.gov/geo/tiger"
# Non-mainland STATEFP to drop (matches the notebook): AK, HI, PR, GU, VI, AS, MP.
MAINLAND_EXCLUDE = ["02", "15", "60", "66", "69", "72", "78"]


def read_zip_shapefile(url: str) -> "gpd.GeoDataFrame":
    LOGGER.info("Downloading %s", url)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(tmp)
        return gpd.read_file(next(Path(tmp).glob("*.shp")))


def detect(cols, candidates):
    return next((c for c in candidates if c in cols), None)


def main():
    ap = argparse.ArgumentParser(description="Counties within/overlapping Metro areas.")
    ap.add_argument("--year", type=int, default=2024, help="TIGER/Line year (fallback layers).")
    ap.add_argument("--metro-layer", type=Path, help="Metro polygon layer (else TIGER CBSA M1).")
    ap.add_argument("--county-layer", type=Path, help="County polygon layer (else TIGER county).")
    ap.add_argument("--metros", nargs="*", help="Restrict to metro id(s) or NAME substrings.")
    ap.add_argument("--keep-dc", action="store_true", help="Keep DC (STATEFP 11).")
    ap.add_argument("--out", type=Path, default=OUT_GPKG)
    ap.add_argument("--regions-csv", type=Path, default=REGIONS_CSV)
    cli = ap.parse_args()

    # --- county layer ---
    counties = (gpd.read_file(cli.county_layer) if cli.county_layer
                else read_zip_shapefile(f"{TIGER}/TIGER{cli.year}/COUNTY/tl_{cli.year}_us_county.zip"))

    # --- metro layer ---
    if cli.metro_layer:
        metros = gpd.read_file(cli.metro_layer)          # assume already metros
    else:
        cbsa = read_zip_shapefile(f"{TIGER}/TIGER{cli.year}/CBSA/tl_{cli.year}_us_cbsa.zip")
        metros = cbsa[cbsa["LSAD"] == "M1"].copy()        # Metropolitan Statistical Areas
    m_id = detect(metros.columns, ["GEOID_METR", "CBSAFP", "GEOID"])
    m_name = detect(metros.columns, ["NAME_METRO", "NAME"])

    if cli.metros:
        keys = [str(m).lower() for m in cli.metros]
        metros = metros[metros.apply(
            lambda r: (m_id and str(r[m_id]) in keys)
            or (m_name and any(k in str(r[m_name]).lower() for k in keys)), axis=1)].copy()
    if metros.empty:
        sys.exit("No metros matched; check --metros / --metro-layer.")
    metros = metros[[c for c in (m_id, m_name, "geometry") if c]].copy()
    LOGGER.info("Metros: %d", len(metros))

    # --- counties within/overlapping metros ---
    counties = counties.to_crs(metros.crs)
    sel = gpd.sjoin(counties, metros, how="inner", predicate="intersects")
    sel = (sel.drop(columns=[c for c in sel.columns if c.startswith("index_")])
              .drop_duplicates(subset="GEOID"))

    # --- mainland filter ---
    drop = set(MAINLAND_EXCLUDE) | ({"11"} if not cli.keep_dc else set())
    sel = sel[~sel["STATEFP"].isin(drop)].copy()
    LOGGER.info("Counties in metros (mainland): %d across %d states",
                len(sel), sel["STATEFP"].nunique())

    cols = ["GEOID", "NAME", "STATEFP", m_id, m_name, "geometry"]
    sel = sel[[c for c in cols if c and c in sel.columns]]
    cli.out.parent.mkdir(parents=True, exist_ok=True)
    sel.to_file(cli.out, driver="GPKG")
    LOGGER.info("Wrote AOI layer -> %s", cli.out)

    cli.regions_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(cli.regions_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["GEOID", "NAME"])
        for _, r in sel.sort_values("GEOID").iterrows():
            w.writerow([r["GEOID"], r.get("NAME", "")])
    LOGGER.info("Wrote %d county GEOIDs -> %s (run_national.sh loops this).",
                len(sel), cli.regions_csv)


if __name__ == "__main__":
    main()
