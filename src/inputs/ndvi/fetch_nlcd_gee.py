#!/usr/bin/env python3
"""
Fetch NLCD Land Cover and/or Tree Canopy Cover (TCC) for San Francisco via GEE.

Feeds the greening-scenario generators:
  - Land Cover -> scenario_lulc_masked.py (--lulc)
  - TCC        -> fit_tcc_ndvi.py (regression for scenario_canopy_target.py)

Uses the same Earth Engine setup as ndvi_gee.py (project default gee-planet-natcap;
browser auth on first run). Exports 30 m GeoTIFFs to the inputs folder.

NOTE on asset IDs: GEE occasionally revises NLCD asset/band names. The defaults
below are the 2021 release; override with --lc-collection / --tcc-collection /
--lc-index / --tcc-band if a load fails. The script prints what it loaded.

REQUIREMENTS  (conda env `snapp`): earthengine-api, geemap
USAGE
    python src/inputs/ndvi/fetch_nlcd_gee.py              # both layers
    python src/inputs/ndvi/fetch_nlcd_gee.py --only tcc   # just TCC
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
LOGGER = logging.getLogger("fetch_nlcd_gee")

INPUTS = Path(__file__).resolve().parents[3] / "data" / "urban-mental-health" / "inputs"
DEFAULT_EE_PROJECT = "gee-planet-natcap"
SF_BBOX = [-122.55, 37.70, -122.35, 37.83]
OUT_CRS = "EPSG:26910"
SCALE_M = 30

# 2021-release defaults (override via CLI if GEE has revised them).
LC_COLLECTION = "USGS/NLCD_RELEASES/2021_REL/NLCD"
LC_INDEX = "2021"
LC_BAND = "landcover"
TCC_COLLECTION = "projects/gtac-data-publish/assets/TCC/Product_Version/2025-6"
TCC_BAND = "Science_Percent_Tree_Canopy_Cover"


def init_ee(project):
    try:
        ee.Initialize(project=project)
    except Exception:
        LOGGER.info("Authenticating with Earth Engine (browser will open)...")
        ee.Authenticate()
        ee.Initialize(project=project)


def export(image, geom, out_path, label):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Exporting %s -> %s", label, out_path)
    geemap.ee_export_image(image, filename=str(out_path), scale=SCALE_M,
                           region=geom, crs=OUT_CRS, file_per_band=False)


def main():
    ap = argparse.ArgumentParser(description="Fetch NLCD Land Cover / TCC for SF via GEE.")
    ap.add_argument("--project", default=os.environ.get("EE_PROJECT", DEFAULT_EE_PROJECT))
    ap.add_argument("--only", choices=["landcover", "tcc"], help="Fetch just one layer.")
    ap.add_argument("--lc-collection", default=LC_COLLECTION)
    ap.add_argument("--lc-index", default=LC_INDEX, help="system:index of the LC year image.")
    ap.add_argument("--lc-band", default=LC_BAND)
    ap.add_argument("--tcc-collection", default=TCC_COLLECTION)
    ap.add_argument("--tcc-band", default=TCC_BAND)
    cli = ap.parse_args()

    init_ee(cli.project)
    geom = ee.Geometry.Rectangle(SF_BBOX)

    if cli.only != "tcc":
        lc = (ee.ImageCollection(cli.lc_collection)
              .filter(ee.Filter.eq("system:index", cli.lc_index)).first())
        if lc is None:
            lc = ee.ImageCollection(cli.lc_collection).mosaic()  # fallback
        lc = lc.select(cli.lc_band).clip(geom)
        export(lc, geom, INPUTS / "nlcd_landcover_sf.tif", "NLCD Land Cover")

    if cli.only != "landcover":
        tcc = (ee.ImageCollection(cli.tcc_collection).select(cli.tcc_band)
               .filterBounds(geom).sort("system:time_start", False).first())
        tcc = tcc.clip(geom)
        export(tcc, geom, INPUTS / "nlcd_tcc_sf.tif", "NLCD Tree Canopy Cover")

    LOGGER.info("Done. Land Cover -> scenario_lulc_masked.py --lulc "
                "data/urban-mental-health/inputs/nlcd_landcover_sf.tif ; "
                "TCC -> fit_tcc_ndvi.py")


if __name__ == "__main__":
    main()
