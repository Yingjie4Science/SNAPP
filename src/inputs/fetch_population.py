#!/usr/bin/env python3
"""
Prepare the InVEST `population_raster` for San Francisco.

Downloads (or reuses) the WorldPop United States 100 m population raster, clips
it to the SF AOI, and reprojects it to a metric CRS.

DATA SOURCE
    WorldPop "United States 100 m Population" (people per pixel, ~100 m, WGS84):
    https://hub.worldpop.org/geodata/listing?id=79
    The national GeoTIFF is large (~hundreds of MB); it's downloaded once into
    data/urban-mental-health/inputs/_worldpop/ and reused on later runs.
    License: CC BY 4.0 (cite WorldPop).

REQUIREMENTS
    pip install rioxarray rasterio geopandas requests

USAGE
    # auto-download the WorldPop US file, then clip to SF:
    python src/inputs/fetch_population.py

    # or point at a file you already downloaded (WorldPop / GHS-POP / GPW):
    python src/inputs/fetch_population.py --pop /path/to/usa_ppp_2020.tif

    # UN-adjusted counts instead of the default:
    python src/inputs/fetch_population.py --unadj

CAVEAT
    Reprojecting counts (people/pixel) is only approximately count-preserving.
    Fine for wiring/testing; for rigorous totals use an area-weighted reprojection.
"""

import argparse
import logging
import sys
from pathlib import Path

import requests

try:
    import geopandas as gpd
    import rioxarray  # noqa: F401  (registers .rio accessor)
    from rasterio.enums import Resampling
except ImportError:
    sys.exit("Missing deps. Install: pip install rioxarray rasterio geopandas requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fetch_population")

BASE_DIR = Path(__file__).resolve().parents[2]
INPUTS = BASE_DIR / "data" / "urban-mental-health" / "inputs"
CACHE = INPUTS / "_worldpop"                         # downloaded national file lives here
DEFAULT_AOI = INPUTS / "sf_aoi.gpkg"                 # from build_aoi_prevalence.py
DEFAULT_OUT = INPUTS / "sf_population.tif"
METRIC_CRS = "EPSG:26910"                            # match the AOI (meters)

# WorldPop US 100 m, 2020 (unconstrained). UNadj = UN-adjusted totals.
# From the listing at https://hub.worldpop.org/geodata/listing?id=79
WORLDPOP_BASE = "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/USA"
WORLDPOP_FILES = {
    "ppp": "usa_ppp_2020.tif",
    "unadj": "usa_ppp_2020_UNadj.tif",
}


def download_worldpop(unadj: bool) -> Path:
    """Download the WorldPop US 100 m file into the cache (skip if present)."""
    fname = WORLDPOP_FILES["unadj" if unadj else "ppp"]
    dest = CACHE / fname
    if dest.exists() and dest.stat().st_size > 0:
        LOGGER.info("Using cached WorldPop file: %s", dest)
        return dest
    CACHE.mkdir(parents=True, exist_ok=True)
    url = f"{WORLDPOP_BASE}/{fname}"
    LOGGER.info("Downloading WorldPop US 100 m (large, one-time): %s", url)
    with requests.get(url, stream=True, timeout=1800) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
        tmp.rename(dest)
    LOGGER.info("Saved %s", dest)
    return dest


def main():
    ap = argparse.ArgumentParser(description="Clip + reproject WorldPop population to SF.")
    ap.add_argument("--pop", type=Path,
                    help="Use an already-downloaded raster instead of fetching WorldPop.")
    ap.add_argument("--unadj", action="store_true",
                    help="Use the UN-adjusted WorldPop file.")
    ap.add_argument("--aoi", type=Path, default=DEFAULT_AOI, help="AOI vector (GPKG).")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output GeoTIFF.")
    cli = ap.parse_args()

    if not cli.aoi.exists():
        sys.exit(f"AOI not found: {cli.aoi}. Run build_aoi_prevalence.py first.")

    pop_path = cli.pop if cli.pop else download_worldpop(cli.unadj)
    if not pop_path.exists():
        sys.exit(f"Population raster not found: {pop_path}")

    aoi = gpd.read_file(cli.aoi)
    pop = rioxarray.open_rasterio(pop_path, masked=True)

    # 1) Clip to the AOI in the raster's own CRS (fast; avoids loading all of USA).
    aoi_in_pop_crs = aoi.to_crs(pop.rio.crs)
    LOGGER.info("Clipping population to SF AOI extent...")
    clipped = pop.rio.clip(aoi_in_pop_crs.geometry, aoi_in_pop_crs.crs, drop=True)

    # 2) Reproject to the metric CRS the model needs (population must be in meters).
    LOGGER.info("Reprojecting to %s...", METRIC_CRS)
    projected = clipped.rio.reproject(METRIC_CRS, resampling=Resampling.bilinear)
    projected = projected.rio.write_nodata(float("nan"))

    cli.output.parent.mkdir(parents=True, exist_ok=True)
    projected.rio.to_raster(cli.output, driver="GTiff", compress="LZW")
    LOGGER.info("Wrote %s (CRS %s, size %s)", cli.output, projected.rio.crs, dict(projected.sizes))
    LOGGER.info("Point the model's `population_raster` at this file.")


if __name__ == "__main__":
    main()
