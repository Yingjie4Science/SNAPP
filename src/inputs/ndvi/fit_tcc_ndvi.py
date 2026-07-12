#!/usr/bin/env python3
"""
Fit a TCC -> NDVI relationship for the canopy-target greening scenario.

Regresses per-tract MEAN NDVI on per-tract MEAN NLCD Tree Canopy Cover (%):
    NDVI = intercept + slope * canopy_percent
The slope/intercept let scenario_canopy_target.py translate a canopy goal (e.g.
30%) into a target NDVI:
    scenario_canopy_target.py --canopy-target 30 --tcc-slope <slope> --tcc-intercept <intercept>

INPUTS
    --ndvi   baseline NDVI raster (default ndvi_base.tif)
    --tcc    NLCD TCC raster (from fetch_nlcd_gee.py: nlcd_tcc.tif)
    --aoi    tract polygons (default aoi.gpkg)

REQUIREMENTS  (conda env `snapp`): geopandas, rioxarray, rasterio, numpy
USAGE
    python src/inputs/ndvi/fit_tcc_ndvi.py
Writes docs/tcc_ndvi_regression.md and prints the ready-to-use scenario command.
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import geopandas as gpd
    import numpy as np
    import rioxarray  # noqa: F401
    from rasterio.features import geometry_mask
except ImportError:
    sys.exit("Missing deps. Install the `snapp` env (geopandas, rioxarray, rasterio, numpy).")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fit_tcc_ndvi")

BASE_DIR = Path(__file__).resolve().parents[3]
INPUTS = BASE_DIR / "data" / "urban-mental-health" / "inputs"
RAW_NLCD = BASE_DIR / "data" / "urban-mental-health" / "raw" / "nlcd"
OUT_MD = BASE_DIR / "docs" / "tcc_ndvi_regression.md"


def tract_means(arr, geoms, shape, transform):
    """Per-geometry mean of a 2-D array, ignoring NaN."""
    out = []
    for g in geoms:
        inside = ~geometry_mask([g], out_shape=shape, transform=transform, invert=False)
        v = arr[inside]
        v = v[~np.isnan(v)]
        out.append(float(v.mean()) if v.size else np.nan)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser(description="Fit tract-mean NDVI ~ tract-mean NLCD TCC.")
    ap.add_argument("--ndvi", type=Path, default=INPUTS / "ndvi_base.tif")
    ap.add_argument("--tcc", type=Path, default=RAW_NLCD / "nlcd_tcc.tif")
    ap.add_argument("--aoi", type=Path, default=INPUTS / "aoi.gpkg")
    cli = ap.parse_args()
    for p in (cli.ndvi, cli.tcc, cli.aoi):
        if not p.exists():
            sys.exit(f"Missing input: {p}  (run fetch_nlcd_gee.py / build_aoi_prevalence.py)")

    ndvi = rioxarray.open_rasterio(cli.ndvi, masked=True).squeeze()
    tcc = rioxarray.open_rasterio(cli.tcc, masked=True).squeeze().rio.reproject_match(ndvi)
    aoi = gpd.read_file(cli.aoi).to_crs(ndvi.rio.crs)

    shape = (ndvi.rio.height, ndvi.rio.width)
    transform = ndvi.rio.transform()
    ndvi_m = tract_means(ndvi.values.astype("float32"), aoi.geometry, shape, transform)
    tcc_m = tract_means(tcc.values.astype("float32"), aoi.geometry, shape, transform)

    ok = ~(np.isnan(ndvi_m) | np.isnan(tcc_m))
    x, y = tcc_m[ok], ndvi_m[ok]
    if x.size < 5:
        sys.exit("Too few valid tracts to regress.")
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    LOGGER.info("NDVI = %.5f + %.5f * canopy%%   (n=%d tracts, R2=%.3f)",
                intercept, slope, x.size, r2)
    cmd = (f"python src/inputs/ndvi/scenario_canopy_target.py --canopy-target 30 "
           f"--tcc-slope {slope:.5f} --tcc-intercept {intercept:.5f}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(
        f"# TCC -> NDVI regression\n\n"
        f"Per-tract mean NDVI on mean NLCD Tree Canopy Cover (%), n={x.size}, "
        f"R^2={r2:.3f}:\n\n"
        f"    NDVI = {intercept:.5f} + {slope:.5f} * canopy_percent\n\n"
        f"Use in the canopy-target scenario (example, 30% goal):\n\n    {cmd}\n")
    LOGGER.info("Wrote %s", OUT_MD)
    print(cmd)


if __name__ == "__main__":
    main()
