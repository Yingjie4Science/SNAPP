#!/usr/bin/env python3
"""
Build the national AOI layer: US COUNTIES that fall within or overlap a
Metropolitan area (Metro / metdiv). County-based adaptation of
00b1-aoi-places-in-metro.ipynb (which used *places*); per project decision the
study unit here is the county intersecting a metro.

METHOD (counties instead of the notebook's places)
    - Load a metro layer and a county layer.
    - Compute, per county, the fraction of its AREA inside a metro (equal-area
      EPSG:5070); keep counties with overlap >= --min-overlap (default 0.30).
      This drops border-touches (0% area) and generalization slivers that a plain
      'intersects' wrongly includes. Each kept county is labelled with its
      dominant (largest-overlap) metro and its overlap_frac.
    - Exclude non-mainland STATEFP ['02','15','60','66','69','72','78'] (AK, HI,
      PR, GU, VI, AS, MP); optionally drop DC ('11').
    - Write data/national/counties.gpkg + config/regions.csv (GEOID list that
      run_national.sh loops).

    Note: CBSAs are officially unions of *whole counties*, so the most rigorous
    membership is the Census delineation crosswalk (county FIPS -> CBSA), not a
    geometry test. The area-overlap threshold is the robust geometric equivalent
    when working from dissolved metro polygons.

LAYERS
    --metro-layer  : your metro shapefile (e.g. the notebook's
        data/aoi/cb_2020_us_metro_combined_metdiv_no_overlap.shp) for an exact
        match. If omitted, the Census CBSA file is downloaded (cartographic
        cb_*_500k by default) and filtered to Metropolitan Statistical Areas
        (LSAD == 'M1').
    --county-layer : a county polygon layer; if omitted, TIGER counties download.
    --crosswalk    : use the official CBSA->county delineation for EXACT whole-
        county membership (no geometry heuristic; overrides the overlap method).
        Bare flag = 2020 Census list1; or pass a path/URL (.xls/.xlsx/.csv).
    --cartographic : DEFAULT — use generalized cb_<year>_us_*_500k files (GENZ
        path); project convention (see docs/data_boundaries.md). Lighter and
        shoreline-clipped; matches the notebook's cb_2020 style (pair with
        --year 2020). Use --no-cartographic for full-res TIGER tl_. Metro id/name
        columns auto-detected (GEOID_METR/NAME_METRO or CBSAFP/NAME).

REQUIREMENTS  (conda env `snapp`): geopandas, pandas, requests
USAGE
    python src/national/build_metro_counties.py \
        --metro-layer data/aoi/cb_2020_us_metro_combined_metdiv_no_overlap.shp
    python src/national/build_metro_counties.py                    # cb_2024 500k (default)
    python src/national/build_metro_counties.py --year 2020        # cb_2020 (match notebook)
    python src/national/build_metro_counties.py --no-cartographic  # full-res TIGER tl_
    python src/national/build_metro_counties.py --crosswalk        # EXACT membership (2020 list1)
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
    import pandas as pd
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge geopandas pandas requests xlrd")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("build_metro_counties")

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_GPKG = BASE_DIR / "data" / "national" / "counties.gpkg"
OUT_METRO = BASE_DIR / "data" / "national" / "metro.gpkg"
REGIONS_CSV = BASE_DIR / "config" / "regions.csv"
TIGER = "https://www2.census.gov/geo/tiger"
# Official OMB/Census CBSA->county delineation (2020). list1 = metro+micro membership.
DEFAULT_DELINEATION = ("https://www2.census.gov/programs-surveys/metro-micro/geographies/"
                       "reference-files/2020/delineation-files/list1_2020.xls")
# Non-mainland STATEFP to drop (matches the notebook): AK, HI, PR, GU, VI, AS, MP.
MAINLAND_EXCLUDE = ["02", "15", "60", "66", "69", "72", "78"]


def read_zip_shapefile(url: str) -> "gpd.GeoDataFrame":
    LOGGER.info("Downloading %s", url)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(tmp)
        return gpd.read_file(next(Path(tmp).glob("*.shp")))


def census_url(kind: str, year: int, cartographic: bool) -> str:
    """URL for a Census 'county' or 'cbsa' layer.

    cartographic=True -> generalized cartographic-boundary file
    (cb_<year>_us_<kind>_500k, GENZ path; matches the notebook's cb_2020 style).
    cartographic=False -> full-resolution TIGER/Line (tl_<year>_us_<kind>).
    """
    if cartographic:
        return f"{TIGER}/GENZ{year}/shp/cb_{year}_us_{kind}_500k.zip"
    sub = {"county": "COUNTY", "cbsa": "CBSA"}[kind]
    return f"{TIGER}/TIGER{year}/{sub}/tl_{year}_us_{kind}.zip"


def detect(cols, candidates):
    return next((c for c in candidates if c in cols), None)


def select_by_overlap(counties, cli):
    """Select counties by AREA-overlap fraction with a metro polygon layer."""
    if cli.metro_layer:
        metros = gpd.read_file(cli.metro_layer)              # assume already metros
    else:
        cbsa = read_zip_shapefile(census_url("cbsa", cli.year, cli.cartographic))
        metros = cbsa[cbsa["LSAD"] == "M1"].copy()            # Metropolitan Stat. Areas
    m_id = detect(metros.columns, ["GEOID_METR", "CBSAFP", "GEOID"])
    m_name = detect(metros.columns, ["NAME_METRO", "NAME"])
    if cli.metros:
        keys = [str(m).lower() for m in cli.metros]
        metros = metros[metros.apply(
            lambda r: (m_id and str(r[m_id]) in keys)
            or (m_name and any(k in str(r[m_name]).lower() for k in keys)), axis=1)].copy()
    if metros.empty:
        sys.exit("No metros matched; check --metros / --metro-layer.")
    metros = metros.rename(columns={m_id: "metro_id", m_name: "metro_name"})
    metros = metros[[c for c in ("metro_id", "metro_name", "geometry") if c in metros.columns]].copy()
    LOGGER.info("Metros: %d", len(metros))

    cli.metro_out.parent.mkdir(parents=True, exist_ok=True)
    metros.to_file(cli.metro_out, driver="GPKG")
    LOGGER.info("Saved metro layer -> %s", cli.metro_out)

    # Overlap fraction in equal-area CRS; keep counties >= --min-overlap.
    EA = "EPSG:5070"
    counties = counties.to_crs(metros.crs)
    c_ea = counties[["GEOID", "geometry"]].to_crs(EA)
    c_ea["county_area"] = c_ea.geometry.area
    inter = gpd.overlay(c_ea, metros.to_crs(EA), how="intersection", keep_geom_type=True)
    inter["ia"] = inter.geometry.area
    dom = (inter.sort_values("ia").drop_duplicates("GEOID", keep="last")
                 .set_index("GEOID")[["metro_id", "metro_name"]])
    frac = (inter.groupby("GEOID")["ia"].sum()
            / c_ea.set_index("GEOID")["county_area"]).rename("overlap_frac")
    stats = dom.join(frac).reset_index()
    stats = stats[stats["overlap_frac"] >= cli.min_overlap]
    LOGGER.info("Counties passing overlap >= %.0f%%: %d (of %d touching a metro)",
                100 * cli.min_overlap, len(stats), inter["GEOID"].nunique())
    sel = counties.merge(stats, on="GEOID", how="inner")
    sel["overlap_frac"] = sel["overlap_frac"].round(4)
    return sel


def select_by_crosswalk(counties, cli):
    """Exact membership via the official CBSA->county delineation crosswalk."""
    src = cli.crosswalk
    LOGGER.info("Reading delineation crosswalk: %s", src)
    read = dict(dtype=str)
    if str(src).lower().endswith(".csv"):
        df = pd.read_csv(src, **read)
    else:
        eng = "xlrd" if str(src).lower().endswith(".xls") else "openpyxl"
        if str(src).startswith("http"):
            r = requests.get(src, timeout=300); r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content), skiprows=2, engine=eng, **read)
        else:
            df = pd.read_excel(src, skiprows=2, engine=eng, **read)

    lut = {c.strip().lower(): c for c in df.columns}

    def col(*names):
        for n in names:
            if n in lut:
                return lut[n]
        sys.exit(f"Crosswalk missing a column among {names}; have {list(df.columns)}")

    metmic = col("metropolitan/micropolitan statistical area")
    df = df[df[metmic].astype(str).str.contains("Metropolitan", na=False)].copy()
    df["GEOID"] = df[col("fips state code")].str.zfill(2) + df[col("fips county code")].str.zfill(3)
    df = (df.rename(columns={col("cbsa code"): "metro_id", col("cbsa title"): "metro_name"})
            [["GEOID", "metro_id", "metro_name"]].dropna(subset=["GEOID"]).drop_duplicates("GEOID"))
    LOGGER.info("Crosswalk metro counties: %d", len(df))
    return counties.merge(df, on="GEOID", how="inner")


def main():
    ap = argparse.ArgumentParser(description="Counties within/overlapping Metro areas.")
    ap.add_argument("--year", type=int, default=2024, help="Census vintage for fallback layers.")
    ap.add_argument("--cartographic", action=argparse.BooleanOptionalAction, default=True,
                    help="Use generalized cartographic-boundary files "
                         "(cb_<year>_us_*_500k) — DEFAULT and project convention "
                         "(see docs/data_boundaries.md). Use --no-cartographic for "
                         "full-res TIGER tl_.")
    ap.add_argument("--metro-layer", type=Path, help="Metro polygon layer (else Census CBSA M1).")
    ap.add_argument("--county-layer", type=Path, help="County polygon layer (else Census county).")
    ap.add_argument("--crosswalk", nargs="?", const=DEFAULT_DELINEATION,
                    default=DEFAULT_DELINEATION,
                    help="DEFAULT membership source: official CBSA->county delineation "
                         "crosswalk (exact whole-county membership, no geometry). Bare flag "
                         "or omitted = 2020 Census list1; or pass a path/URL "
                         "(.xls/.xlsx/.csv). Ignored if --overlap is set.")
    ap.add_argument("--overlap", action="store_true",
                    help="Use the geometry AREA-overlap method instead of the crosswalk "
                         "(needs a metro polygon layer; honours --min-overlap).")
    ap.add_argument("--metros", nargs="*", help="Restrict to metro id(s) or NAME substrings (overlap mode).")
    ap.add_argument("--min-overlap", type=float, default=0.30,
                    help="Overlap mode: keep a county only if this fraction of its area "
                         "falls inside a metro (0-1). Default 0.30; insensitive ~0.05-0.90.")
    ap.add_argument("--keep-dc", action="store_true", help="Keep DC (STATEFP 11).")
    ap.add_argument("--out", type=Path, default=OUT_GPKG)
    ap.add_argument("--regions-csv", type=Path, default=REGIONS_CSV)
    ap.add_argument("--metro-out", type=Path, default=OUT_METRO,
                    help="Save a copy of the metro layer used (provenance/reuse).")
    cli = ap.parse_args()

    # --- county layer ---
    counties = (gpd.read_file(cli.county_layer) if cli.county_layer
                else read_zip_shapefile(census_url("county", cli.year, cli.cartographic)))

    # --- select metro counties: exact crosswalk (default) or area-overlap ---
    if cli.overlap:
        sel = select_by_overlap(counties, cli)
    else:
        sel = select_by_crosswalk(counties, cli)

    # --- mainland filter ---
    drop = set(MAINLAND_EXCLUDE) | ({"11"} if not cli.keep_dc else set())
    sel = sel[~sel["STATEFP"].isin(drop)].copy()
    LOGGER.info("Counties in metros (mainland): %d across %d states",
                len(sel), sel["STATEFP"].nunique())

    cols = ["GEOID", "NAME", "STATEFP", "metro_id", "metro_name", "overlap_frac", "geometry"]
    sel = sel[[c for c in cols if c in sel.columns]]
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
