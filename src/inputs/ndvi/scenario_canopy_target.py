#!/usr/bin/env python3
"""
POLICY-HEADLINE greening scenario: per-tract canopy / NDVI target.

Raises NDVI within each tract so the tract's MEAN NDVI reaches a target — a
policy-interpretable scenario ("every neighborhood reaches target greenness").
The target can be given directly as an NDVI value, or derived from a tree-canopy
goal via a linear TCC->NDVI relationship (NDVI = intercept + slope * canopy%).

Method: per tract, delta = max(0, target_ndvi - current_mean_ndvi); add delta to
every pixel in the tract (raise only, never lower), capped. Optionally restrict
the raise to greenable pixels with --lulc (same idea as scenario_lulc_masked).

Because your Landsat NDVI is built to align with NLCD Tree Canopy Cover, you can
estimate slope/intercept by regressing tract-mean NDVI on tract-mean TCC and pass
them here; otherwise set --target-ndvi directly.

REQUIREMENTS  (conda env `snapp`): geopandas, rioxarray, rasterio, xarray, numpy

USAGE
    # direct NDVI target for every tract:
    python src/inputs/ndvi/scenario_canopy_target.py --target-ndvi 0.60
    # from a 30% canopy goal via a TCC->NDVI regression you fit:
    python src/inputs/ndvi/scenario_canopy_target.py --canopy-target 30 --tcc-slope 0.012 --tcc-intercept 0.15
Then point the model's ndvi_alt at the output (config.yaml -> inputs.ndvi_alt).
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
LOGGER = logging.getLogger("scenario_canopy_target")

INPUTS = Path(__file__).resolve().parents[3] / "data" / "urban-mental-health" / "inputs"
DEFAULT_BASE = INPUTS / "ndvi_base.tif"
DEFAULT_AOI = INPUTS / "aoi.gpkg"
DEFAULT_OUT = INPUTS / "ndvi_scenario_canopy.tif"


def resolve_target(cli) -> float:
    """Target tract-mean NDVI, either given directly or from a canopy goal."""
    if cli.target_ndvi is not None:
        return cli.target_ndvi
    if cli.canopy_target is not None and cli.tcc_slope is not None:
        return cli.tcc_intercept + cli.tcc_slope * cli.canopy_target
    sys.exit("Provide --target-ndvi, or --canopy-target with --tcc-slope/--tcc-intercept.")


def main():
    ap = argparse.ArgumentParser(description="Per-tract canopy/NDVI-target scenario.")
    ap.add_argument("--ndvi-base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--aoi", type=Path, default=DEFAULT_AOI, help="Tract polygons (GPKG).")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--target-ndvi", type=float, help="Target tract-mean NDVI (direct).")
    ap.add_argument("--canopy-target", type=float, help="Canopy goal in %% (needs slope/intercept).")
    ap.add_argument("--tcc-slope", type=float, help="NDVI per 1%% canopy (regression slope).")
    ap.add_argument("--tcc-intercept", type=float, default=0.0, help="Regression intercept.")
    ap.add_argument("--cap", type=float, default=0.90, help="Absolute NDVI ceiling.")
    cli = ap.parse_args()

    if not cli.ndvi_base.exists():
        sys.exit(f"NDVI base not found: {cli.ndvi_base}")
    if not cli.aoi.exists():
        sys.exit(f"AOI not found: {cli.aoi}. Run build_aoi_prevalence.py first.")

    target = resolve_target(cli)
    LOGGER.info("Per-tract target mean NDVI = %.3f", target)

    base = rioxarray.open_rasterio(cli.ndvi_base, masked=True).squeeze()
    aoi = gpd.read_file(cli.aoi).to_crs(base.rio.crs)
    transform = base.rio.transform()
    shape = (base.rio.height, base.rio.width)
    arr = base.values.astype("float32")               # 2-D NDVI array
    out = arr.copy()

    raised_tracts = 0
    for geom in aoi.geometry:
        # Pixels inside this tract (geometry_mask: True = OUTSIDE, so invert).
        inside = ~geometry_mask([geom], out_shape=shape, transform=transform, invert=False)
        vals = arr[inside]
        valid = vals[~np.isnan(vals)]
        if valid.size == 0:
            continue
        delta = max(0.0, target - float(valid.mean()))
        if delta > 0:
            out[inside] = np.where(np.isnan(arr[inside]), np.nan,
                                   np.minimum(arr[inside] + delta, cli.cap))
            raised_tracts += 1

    alt = base.copy(data=out)
    alt = alt.rio.write_crs(base.rio.crs)
    alt.rio.write_nodata(float("nan"), inplace=True)
    alt.attrs.pop("_FillValue", None)

    cli.output.parent.mkdir(parents=True, exist_ok=True)
    alt.rio.to_raster(cli.output, driver="GTiff", compress="LZW")
    LOGGER.info("Tracts raised: %d/%d | mean NDVI %.3f -> %.3f",
                raised_tracts, len(aoi), float(np.nanmean(arr)), float(np.nanmean(out)))
    LOGGER.info("Wrote %s — set config.yaml inputs.ndvi_alt to this file.", cli.output)


if __name__ == "__main__":
    main()
