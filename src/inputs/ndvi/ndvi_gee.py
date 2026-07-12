#!/usr/bin/env python3
"""
NDVI via Google Earth Engine — Python port of your Landsat Code Editor script,
adapted for San Francisco and the InVEST `ndvi_base` input.

METHODOLOGY (kept faithful to your original script)
    - Sensors: Landsat 5, 7, 8 Collection-2 Level-2 (L9 added for recent years).
    - Season: June-September only (calendarRange 6-9), to align with NLCD TCC.
    - Composite: annual 90th percentile ("peak greenness" during the growing
      season) — not mean/median.
    - Scaling: Landsat C2 L2 scale factors applied before NDVI.
    - Clouds: QA_PIXEL bits 0-4 must be clear; QA_RADSAT for L8/9 saturation.
    - NDVI bands: L5/7 = (SR_B4-SR_B3)/(SR_B4+SR_B3); L8/9 = (SR_B5-SR_B4)/(...).
    - Resolution: 30 m.
    Difference vs. your original: this exports ONE year clipped to SF as a single
    float GeoTIFF for the model (your script also wrote an Int16 x100 copy and
    looped over many city AOIs).

PREREQUISITES
    - Google account with Earth Engine enabled + a Cloud project id
      (https://code.earthengine.google.com). First run opens a browser to auth.
REQUIREMENTS
    conda install -c conda-forge earthengine-api geemap   # in environment.yml

USAGE
    python src/inputs/ndvi/ndvi_gee.py --project YOUR_EE_PROJECT_ID           # 2024, local file
    python src/inputs/ndvi/ndvi_gee.py --project ID --year 2021              # a different year
    python src/inputs/ndvi/ndvi_gee.py --project ID --to-drive              # Export.image.toDrive
"""

import argparse
import logging
import os
import sys
from pathlib import Path

try:
    import ee
    import geemap
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge earthengine-api geemap")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("ndvi_gee")

BASE_DIR = Path(__file__).resolve().parents[3]
OUT = BASE_DIR / "data" / "urban-mental-health" / "inputs" / "sf_ndvi_2024_gee.tif"

# Default Earth Engine Cloud project (override with --project or env EE_PROJECT).
DEFAULT_EE_PROJECT = "gee-planet-natcap"

SF_BBOX = [-122.55, 37.70, -122.35, 37.83]   # [west, south, east, north] WGS84
OUT_CRS = "EPSG:26910"                         # meters, matches the AOI
SCALE_M = 30                                    # Landsat native resolution
SEASON = (6, 9)                                 # June-September (JJAS)
FULL_START, FULL_END = "1986-01-01", "2025-12-31"
L7_WINDOW = ("2012-04-01", "2013-04-01")       # only trust L7 here (SLC-off strips)


# --- masking / scaling (ported from the Code Editor script) ---
def apply_scale_factors(image):
    optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
    thermal = image.select("ST_B.*").multiply(0.00341802).add(149.0)
    return image.addBands(optical, None, True).addBands(thermal, None, True)


def _clear_qa_mask(image):
    # Keep pixels where QA_PIXEL bits 0-4 (fill/dilated/cirrus/cloud/shadow) are 0.
    return image.select("QA_PIXEL").bitwiseAnd(int("11111", 2)).eq(0)


def mask_l457(image):
    return image.updateMask(_clear_qa_mask(image))


def mask_l89(image):
    sat = image.select("QA_RADSAT").eq(0)
    return (image.updateMask(_clear_qa_mask(image)).updateMask(sat)
            .select("SR_B[0-9]*").copyProperties(image, ["system:time_start"]))


def add_ndvi_l57(image):
    return image.addBands(image.normalizedDifference(["SR_B4", "SR_B3"]).rename("NDVI"))


def add_ndvi_l89(image):
    return image.addBands(image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI"))


def build_ndvi_collection(geom):
    """Merged JJAS NDVI collection across Landsat 5/7/8/9 (scaled, cloud-masked)."""
    season = ee.Filter.calendarRange(SEASON[0], SEASON[1], "month")

    def prep(coll_id, start, end):
        return (ee.ImageCollection(coll_id)
                .filterDate(start, end).filter(season).filterBounds(geom)
                .map(lambda im: im.clip(geom)).map(apply_scale_factors))

    l5 = prep("LANDSAT/LT05/C02/T1_L2", FULL_START, FULL_END).map(mask_l457).map(add_ndvi_l57)
    l7 = prep("LANDSAT/LE07/C02/T1_L2", *L7_WINDOW).map(mask_l457).map(add_ndvi_l57)
    l8 = prep("LANDSAT/LC08/C02/T1_L2", FULL_START, FULL_END).map(mask_l89).map(add_ndvi_l89)
    l9 = prep("LANDSAT/LC09/C02/T1_L2", FULL_START, FULL_END).map(mask_l89).map(add_ndvi_l89)

    return l5.merge(l7).merge(l8).merge(l9).select("NDVI")


def yearly_p90(ndvi_coll, geom, year):
    """Annual 90th-percentile NDVI (peak growing-season greenness) for one year."""
    start = ee.Date.fromYMD(year, 1, 1)
    return (ndvi_coll.filterDate(start, start.advance(1, "year"))
            .filter(ee.Filter.calendarRange(SEASON[0], SEASON[1], "month"))
            .reduce(ee.Reducer.percentile([90])).rename("NDVI")
            .clip(geom))


def init_ee(project):
    try:
        ee.Initialize(project=project)
    except Exception:
        LOGGER.info("Authenticating with Earth Engine (browser will open)...")
        ee.Authenticate()
        ee.Initialize(project=project)


def main():
    ap = argparse.ArgumentParser(description="GEE Landsat JJAS p90 NDVI for SF.")
    ap.add_argument("--project", default=os.environ.get("EE_PROJECT", DEFAULT_EE_PROJECT),
                    help=f"Earth Engine Cloud project id (default: {DEFAULT_EE_PROJECT}).")
    ap.add_argument("--year", type=int, default=2024, help="Year to composite (default 2024).")
    ap.add_argument("--output", type=Path, default=OUT, help="Local output GeoTIFF.")
    ap.add_argument("--to-drive", action="store_true",
                    help="Export to Google Drive instead of downloading locally.")
    cli = ap.parse_args()

    if not cli.project:
        sys.exit("Provide --project YOUR_EE_PROJECT_ID (or set EE_PROJECT). "
                  "Find/create one at https://code.earthengine.google.com")

    init_ee(cli.project)
    geom = ee.Geometry.Rectangle(SF_BBOX)
    ndvi = yearly_p90(build_ndvi_collection(geom), geom, cli.year)

    if cli.to_drive:
        desc = f"NDVI_p90_landsat_30m_{cli.year}_SF"
        task = ee.batch.Export.image.toDrive(
            image=ndvi, description=desc, folder="gee_ndvi_sf",
            fileNamePrefix=desc, region=geom, scale=SCALE_M,
            maxPixels=int(1e13), fileFormat="GeoTIFF",
            formatOptions={"noData": -9999.0},
        )
        task.start()
        LOGGER.info("Started Drive export '%s' (folder gee_ndvi_sf). "
                    "Track it at https://code.earthengine.google.com/tasks", desc)
    else:
        out = cli.output if cli.year == 2024 else cli.output.with_name(
            f"sf_ndvi_{cli.year}_gee.tif")
        out.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Downloading NDVI -> %s (scale %dm, %s)...", out, SCALE_M, OUT_CRS)
        geemap.ee_export_image(ndvi, filename=str(out), scale=SCALE_M,
                               region=geom, crs=OUT_CRS, file_per_band=False)
        LOGGER.info("Done. Point the model's `ndvi_base` at %s", out)


if __name__ == "__main__":
    main()
