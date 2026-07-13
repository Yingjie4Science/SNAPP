#!/usr/bin/env python3
"""
Make an `ndvi_alt` greening-scenario raster from the baseline NDVI (`ndvi_base`).

The InVEST Urban Mental Health model compares a baseline against an alternate
scenario; this builds that alternate by increasing greenness. Two modes:

  uniform        add a fixed increment to every valid pixel (simple sensitivity run)
  greenable      only raise pixels currently BELOW a target (a more realistic
                 "green the un-green areas" scenario); already-green pixels unchanged
  best_potential raise every pixel below this AOI's OWN Nth-percentile NDVI up to
                 that percentile ("make each neighborhood as green as the greenest
                 parts of THIS city"). Uses the city's own distribution, so it is
                 climate-/region-fair — a dry city isn't asked to match a wet one.
                 (Adapts Wu et al. 2026, but per-city rather than cross-city.)

All modes cap the result so NDVI can't exceed a physical/plausible max.

REQUIREMENTS
    conda env: rioxarray, rasterio, xarray, numpy   (already in environment.yml)

USAGE
    # uniform +0.05 greening, capped at 0.90 (default input = GEE NDVI):
    python src/inputs/ndvi/make_ndvi_scenario.py

    # green only pixels below 0.6, raising them by 0.10:
    python src/inputs/ndvi/make_ndvi_scenario.py --mode greenable --delta 0.10 --target 0.60

    # best-potential: level every pixel up to this city's own 95th-percentile NDVI:
    python src/inputs/ndvi/make_ndvi_scenario.py --mode best_potential --percentile 95 \
        --output data/urban-mental-health/inputs/ndvi_scenario_bestpot.tif

    # use a different baseline (e.g. the openEO / composite raster):
    python src/inputs/ndvi/make_ndvi_scenario.py --input data/urban-mental-health/inputs/ndvi_base_copernicus.tif
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

INPUTS = Path(__file__).resolve().parents[3] / "data" / "urban-mental-health" / "inputs"
DEFAULT_IN = INPUTS / "ndvi_base.tif"      # the GEE baseline (route in use)
DEFAULT_OUT = INPUTS / "ndvi_scenario.tif"     # matches run_model.py's ndvi_alt


def main():
    ap = argparse.ArgumentParser(description="Build an ndvi_alt greening scenario.")
    ap.add_argument("--input", type=Path, default=DEFAULT_IN, help="Baseline NDVI raster.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Scenario NDVI raster.")
    ap.add_argument("--mode", choices=["uniform", "greenable", "best_potential"],
                    default="uniform")
    ap.add_argument("--delta", type=float, default=0.05, help="NDVI increase to apply.")
    ap.add_argument("--cap", type=float, default=0.90, help="Max NDVI after greening.")
    ap.add_argument("--target", type=float, default=0.60,
                    help="greenable mode: only raise pixels below this NDVI.")
    ap.add_argument("--percentile", type=float, default=95.0,
                    help="best_potential mode: within-AOI NDVI percentile to level up to.")
    cli = ap.parse_args()

    if not cli.input.exists():
        sys.exit(f"Baseline NDVI not found: {cli.input}. Generate ndvi_base first.")

    base = rioxarray.open_rasterio(cli.input, masked=True).squeeze()

    # Build the alternate (greened) NDVI per mode.
    if cli.mode == "uniform":
        alt = base + cli.delta
    elif cli.mode == "greenable":                # increment only below the target
        alt = base + xr.where(base < cli.target, cli.delta, 0.0)
    else:                                        # best_potential: level up to this AOI's own Pth pct
        pval = float(np.nanpercentile(base.values, cli.percentile))
        alt = xr.where(base < pval, pval, base)  # raise below-target pixels; greener unchanged
        LOGGER.info("best_potential: AOI p%.0f NDVI = %.3f (leveling floor)", cli.percentile, pval)

    alt = alt.clip(max=cli.cap)                  # cap NDVI
    alt = alt.where(~base.isnull())              # preserve nodata footprint

    # Restore geospatial metadata (arithmetic can drop it).
    alt = alt.rio.write_crs(base.rio.crs)
    alt = alt.rio.write_nodata(float("nan"))

    cli.output.parent.mkdir(parents=True, exist_ok=True)
    alt.rio.to_raster(cli.output, driver="GTiff", compress="LZW")

    # Report what changed (sanity check).
    diff = (alt - base)
    changed = int((diff > 0).sum())
    extra = (f" target={cli.target}" if cli.mode == "greenable"
             else f" percentile={cli.percentile}" if cli.mode == "best_potential" else "")
    LOGGER.info("mode=%s delta=%s cap=%s%s", cli.mode, cli.delta, cli.cap, extra)
    LOGGER.info("pixels increased: %d | mean NDVI %.3f -> %.3f",
                changed, float(base.mean()), float(alt.mean()))
    LOGGER.info("Wrote %s (use as the model's ndvi_alt)", cli.output)


if __name__ == "__main__":
    main()
