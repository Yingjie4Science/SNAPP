#!/usr/bin/env python3
"""
Make an `ndvi_alt` greening-scenario raster from the baseline NDVI (`ndvi_base`).

The InVEST Urban Mental Health model compares a baseline against an alternate
scenario; this builds that alternate by increasing greenness. Two modes:

  uniform    add a fixed increment to every valid pixel (simple sensitivity run)
  greenable  only raise pixels currently BELOW a target (a more realistic
             "green the un-green areas" scenario); already-green pixels unchanged

Both cap the result so NDVI can't exceed a physical/plausible max.

REQUIREMENTS
    conda env: rioxarray, rasterio, xarray, numpy   (already in environment.yml)

USAGE
    # uniform +0.05 greening, capped at 0.90 (default input = GEE NDVI):
    python src/inputs/make_ndvi_scenario.py

    # green only pixels below 0.6, raising them by 0.10:
    python src/inputs/make_ndvi_scenario.py --mode greenable --delta 0.10 --target 0.60

    # use a different baseline (e.g. the openEO / composite raster):
    python src/inputs/make_ndvi_scenario.py --input data/urban-mental-health/inputs/sf_ndvi_2024_mean.tif
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import numpy as np
    import rioxarray  # noqa: F401  (registers .rio accessor)
    import xarray as xr
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge rioxarray rasterio xarray")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("make_ndvi_scenario")

INPUTS = Path(__file__).resolve().parents[2] / "data" / "urban-mental-health" / "inputs"
DEFAULT_IN = INPUTS / "sf_ndvi_2024_gee.tif"      # the GEE baseline (route in use)
DEFAULT_OUT = INPUTS / "sf_ndvi_scenario.tif"     # matches run_model.py's ndvi_alt


def main():
    ap = argparse.ArgumentParser(description="Build an ndvi_alt greening scenario.")
    ap.add_argument("--input", type=Path, default=DEFAULT_IN, help="Baseline NDVI raster.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Scenario NDVI raster.")
    ap.add_argument("--mode", choices=["uniform", "greenable"], default="uniform")
    ap.add_argument("--delta", type=float, default=0.05, help="NDVI increase to apply.")
    ap.add_argument("--cap", type=float, default=0.90, help="Max NDVI after greening.")
    ap.add_argument("--target", type=float, default=0.60,
                    help="greenable mode: only raise pixels below this NDVI.")
    cli = ap.parse_args()

    if not cli.input.exists():
        sys.exit(f"Baseline NDVI not found: {cli.input}. Generate ndvi_base first.")

    base = rioxarray.open_rasterio(cli.input, masked=True).squeeze()

    # Apply the greening increment.
    if cli.mode == "uniform":
        increment = cli.delta
    else:  # greenable: increment only where baseline is below the target
        increment = xr.where(base < cli.target, cli.delta, 0.0)

    alt = (base + increment).clip(max=cli.cap)   # cap NDVI
    alt = alt.where(~base.isnull())              # preserve nodata footprint

    # Restore geospatial metadata (arithmetic can drop it).
    alt = alt.rio.write_crs(base.rio.crs)
    alt = alt.rio.write_nodata(float("nan"))

    cli.output.parent.mkdir(parents=True, exist_ok=True)
    alt.rio.to_raster(cli.output, driver="GTiff", compress="LZW")

    # Report what changed (sanity check).
    diff = (alt - base)
    changed = int((diff > 0).sum())
    LOGGER.info("mode=%s delta=%s cap=%s%s", cli.mode, cli.delta, cli.cap,
                f" target={cli.target}" if cli.mode == "greenable" else "")
    LOGGER.info("pixels increased: %d | mean NDVI %.3f -> %.3f",
                changed, float(base.mean()), float(alt.mean()))
    LOGGER.info("Wrote %s (use as the model's ndvi_alt)", cli.output)


if __name__ == "__main__":
    main()
