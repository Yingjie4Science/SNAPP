#!/usr/bin/env python3
"""
Prepare the InVEST `population_raster` for San Francisco.

Downloads (or reuses) the WorldPop United States 100 m population raster, clips
it to the SF AOI, and reprojects it to a metric CRS.

DATA SOURCE
    WorldPop "Global 2015-2030" (Global2), release R2025A — constrained US
    population per 100 m pixel, available per year 2015-2030 (so 2024 exists):
    https://hub.worldpop.org/geodata/listing?id=135
    The national GeoTIFF is large (~hundreds of MB); it's downloaded once into
    data/urban-mental-health/inputs/_worldpop/ and reused on later runs.
    License: CC BY 4.0 (cite WorldPop).

REQUIREMENTS
    pip install rioxarray rasterio geopandas requests

USAGE
    # auto-download the WorldPop US 2024 file, then clip to SF:
    python src/inputs/fetch_population.py

    # a different year (2015-2030):
    python src/inputs/fetch_population.py --year 2020

    # if the auto URL 404s, copy the exact link from the listing page:
    python src/inputs/fetch_population.py --url https://data.worldpop.org/.../usa_pop_2024_...tif

    # or point at a file you already downloaded (WorldPop / GHS-POP / GPW):
    python src/inputs/fetch_population.py --pop /path/to/usa_pop_2024.tif

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

# WorldPop "Global 2015-2030" (Global2), constrained 100 m, listing id=135.
# Path/name follow the R2025A convention; verify on the listing page if it 404s.
WORLDPOP_RELEASE = "R2025A"
DEFAULT_YEAR = 2024


def worldpop_url(year: int) -> tuple[str, str]:
    """Best-effort direct URL + filename for the US constrained file of `year`."""
    base = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/"
            f"{WORLDPOP_RELEASE}/{year}/USA/v1/100m/constrained")
    fname = f"usa_pop_{year}_CN_100m_{WORLDPOP_RELEASE}_v1.tif"
    return f"{base}/{fname}", fname


def download_worldpop(year: int, url_override: str | None) -> Path:
    """Download the WorldPop US file into the cache (skip if already present)."""
    if url_override:
        url, fname = url_override, url_override.rsplit("/", 1)[-1]
    else:
        url, fname = worldpop_url(year)
    dest = CACHE / fname
    if dest.exists() and dest.stat().st_size > 0:
        LOGGER.info("Using cached WorldPop file: %s", dest)
        return dest
    CACHE.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading WorldPop US 100 m (large, one-time): %s", url)
    try:
        with requests.get(url, stream=True, timeout=1800) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
            tmp.rename(dest)
    except requests.HTTPError as e:
        sys.exit(
            f"WorldPop download failed ({e}).\n"
            "The R2025A path may differ. Copy the exact US GeoTIFF link from\n"
            "  https://hub.worldpop.org/geodata/listing?id=135\n"
            "and pass it with --url, or download it and pass --pop <file>."
        )
    LOGGER.info("Saved %s", dest)
    return dest


def main():
    ap = argparse.ArgumentParser(description="Clip + reproject WorldPop population to SF.")
    ap.add_argument("--pop", type=Path,
                    help="Use an already-downloaded raster instead of fetching WorldPop.")
    ap.add_argument("--url", help="Exact WorldPop GeoTIFF URL (overrides the auto path).")
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR,
                    help=f"WorldPop year, 2015-2030 (default {DEFAULT_YEAR}).")
    ap.add_argument("--aoi", type=Path, default=DEFAULT_AOI, help="AOI vector (GPKG).")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output GeoTIFF.")
    cli = ap.parse_args()

    if not cli.aoi.exists():
        sys.exit(f"AOI not found: {cli.aoi}. Run build_aoi_prevalence.py first.")

    pop_path = cli.pop if cli.pop else download_worldpop(cli.year, cli.url)
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
