#!/usr/bin/env python3
"""
PRIMARY greening scenario: LULC-masked NDVI increase.

Raises NDVI only on *greenable* land-cover classes (developed open space, low-
intensity developed, barren) toward a target, leaving water, wetlands, and
already-green/high-canopy pixels unchanged. This avoids the main artifact of the
uniform scenario (greening rooftops and water). Output stays an NDVI raster, so
the model runs with model_option='ndvi' as usual.

INPUT DATA you supply
    --lulc : an NLCD Land Cover raster covering the AOI (30 m; free from MRLC,
             https://www.mrlc.gov/data). Any CRS — it's reprojected to the NDVI grid.

GREENABLE CLASSES (NLCD codes, override with --greenable)
    21 Developed, Open Space | 22 Developed, Low Intensity | 31 Barren Land
    (Excluded by default: 11 water, 90/95 wetlands, 41-43 forest, 23/24 dense
    developed, 81/82 cropland/pasture — i.e. not realistically "greenable".)

REQUIREMENTS  (conda env `snapp`): rioxarray, rasterio, xarray, numpy

USAGE
    python src/inputs/ndvi/scenario_lulc_masked.py --lulc data/.../nlcd_sf.tif
    # tune: --target 0.65 --delta 0.15 --cap 0.90
Then point the model's ndvi_alt at the output (config.yaml -> inputs.ndvi_alt).
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import numpy as np
    import rioxarray  # noqa: F401
    import xarray as xr
except ImportError:
    sys.exit("Missing deps. Install the `snapp` env (rioxarray, rasterio, xarray, numpy).")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("scenario_lulc_masked")

INPUTS = Path(__file__).resolve().parents[3] / "data" / "urban-mental-health" / "inputs"
DEFAULT_BASE = INPUTS / "sf_ndvi_2024_gee.tif"
DEFAULT_OUT = INPUTS / "sf_ndvi_scenario_lulc.tif"
GREENABLE_DEFAULT = [21, 22, 31]


def main():
    ap = argparse.ArgumentParser(description="LULC-masked greening scenario (ndvi_alt).")
    ap.add_argument("--ndvi-base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--lulc", type=Path, required=True, help="NLCD Land Cover raster.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--greenable", type=int, nargs="+", default=GREENABLE_DEFAULT,
                    help="NLCD codes eligible for greening.")
    ap.add_argument("--target", type=float, default=0.65,
                    help="NDVI level greenable pixels are raised toward (cap per pixel).")
    ap.add_argument("--delta", type=float, default=0.15,
                    help="Max NDVI increase applied to a greenable pixel.")
    ap.add_argument("--cap", type=float, default=0.90, help="Absolute NDVI ceiling.")
    cli = ap.parse_args()

    if not cli.ndvi_base.exists():
        sys.exit(f"NDVI base not found: {cli.ndvi_base}")
    if not cli.lulc.exists():
        sys.exit(f"LULC raster not found: {cli.lulc} (download NLCD from mrlc.gov).")

    base = rioxarray.open_rasterio(cli.ndvi_base, masked=True).squeeze()
    lulc = rioxarray.open_rasterio(cli.lulc, masked=True).squeeze()
    # Align LULC to the NDVI grid (nearest — categorical data).
    lulc = lulc.rio.reproject_match(base, resampling=0)  # 0 = nearest

    greenable = xr.zeros_like(base, dtype=bool)
    for code in cli.greenable:
        greenable = greenable | (lulc == code)

    # Greenable pixels: bump by delta but not past the target; never lower NDVI.
    bumped = xr.where(base < cli.target, np.minimum(base + cli.delta, cli.target), base)
    alt = xr.where(greenable, bumped, base).clip(max=cli.cap)
    alt = alt.where(~base.isnull())
    alt = alt.rio.write_crs(base.rio.crs)
    alt.rio.write_nodata(float("nan"), inplace=True)
    alt.attrs.pop("_FillValue", None)

    cli.output.parent.mkdir(parents=True, exist_ok=True)
    alt.rio.to_raster(cli.output, driver="GTiff", compress="LZW")

    changed = int(((alt - base) > 1e-6).sum())
    LOGGER.info("Greenable codes %s | pixels raised: %d | mean NDVI %.3f -> %.3f",
                cli.greenable, changed, float(base.mean()), float(alt.mean()))
    LOGGER.info("Wrote %s — set config.yaml inputs.ndvi_alt to this file.", cli.output)


if __name__ == "__main__":
    main()
