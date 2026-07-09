#!/usr/bin/env python3
"""
Composite the 2024 SF NDVI dekad files into ONE annual-mean GeoTIFF.

WHY
    download.py produces 36 clipped 10-daily ("dekad") NetCDFs in
    data/sf-ndvi-2024/processed/. The InVEST Urban Mental Health model wants a
    single NDVI raster for `ndvi_base`, so we average the dekads over time and
    write a GeoTIFF straight into the model's inputs folder.

FLOW
    data/sf-ndvi-2024/processed/*.nc  --(annual mean)-->  ndvi_base GeoTIFF
    default output: data/urban-mental-health/inputs/sf_ndvi_2024_mean.tif

REQUIREMENTS
    pip install xarray netCDF4 rioxarray rasterio

USAGE
    python src/sf_ndvi/composite_ndvi.py                 # use project defaults
    python src/sf_ndvi/composite_ndvi.py --reproject EPSG:3310   # optional: to meters
"""

import argparse
import logging
import sys
from pathlib import Path

import xarray as xr

try:
    import rioxarray  # noqa: F401  (registers the .rio accessor on xarray objects)
except ImportError:
    sys.exit("Missing rioxarray/rasterio. Install: pip install rioxarray rasterio")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("composite_ndvi")

# --- project paths (this file lives in <project>/src/sf_ndvi/) ---
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_IN = BASE_DIR / "data" / "sf-ndvi-2024" / "processed"
DEFAULT_OUT = BASE_DIR / "data" / "urban-mental-health" / "inputs" / "sf_ndvi_2024_mean.tif"

# Coordinate name candidates, in priority order.
LON_NAMES = ("lon", "longitude", "x")
LAT_NAMES = ("lat", "latitude", "y")


def pick(names, available):
    """Return the first candidate name that exists in `available`, else None."""
    return next((n for n in names if n in available), None)


def ndvi_var(ds: xr.Dataset) -> str:
    """Find the NDVI variable, preferring a name that looks like NDVI."""
    for cand in ("NDVI", "ndvi"):
        if cand in ds.data_vars:
            return cand
    # Fallback: the single (or first) data variable in the file.
    return list(ds.data_vars)[0]


def main():
    ap = argparse.ArgumentParser(description="Annual-mean NDVI GeoTIFF from dekad NetCDFs.")
    ap.add_argument("--input-dir", type=Path, default=DEFAULT_IN,
                    help=f"Folder of clipped dekad .nc files (default: {DEFAULT_IN})")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT,
                    help=f"Output GeoTIFF path (default: {DEFAULT_OUT})")
    ap.add_argument("--reproject", metavar="EPSG",
                    help="Optional target CRS (e.g. EPSG:3310) to reproject into meters.")
    args = ap.parse_args()

    files = sorted(args.input_dir.glob("*.nc"))
    if not files:
        sys.exit(f"No .nc files in {args.input_dir}. Run download.py first.")
    LOGGER.info("Compositing %d dekad files from %s", len(files), args.input_dir)

    # Open each dekad (open_dataset decodes CF scale/offset -> physical NDVI),
    # then stack along time. Opening per-file avoids a hard dask dependency.
    var = ndvi_var(xr.open_dataset(files[0]))
    layers = [xr.open_dataset(f)[var] for f in files]
    stacked = xr.concat(layers, dim="time")          # shape: (time, lat, lon)

    # Annual mean, ignoring gaps (clouds/snow are stored as NaN after decoding).
    mean = stacked.mean(dim="time", skipna=True)

    # Tell rioxarray which dims are spatial, and set the CRS.
    lon = pick(LON_NAMES, mean.dims)
    lat = pick(LAT_NAMES, mean.dims)
    if not (lon and lat):
        sys.exit(f"Could not identify lon/lat dims in {tuple(mean.dims)}")
    mean = mean.rio.set_spatial_dims(x_dim=lon, y_dim=lat)
    if mean.rio.crs is None:
        mean = mean.rio.write_crs("EPSG:4326")        # CGLS NDVI is lon/lat WGS84
    mean = mean.rio.write_nodata(float("nan"))

    # Optional: reproject to a metric CRS (handy so all model rasters align).
    if args.reproject:
        mean = mean.rio.reproject(args.reproject)
        LOGGER.info("Reprojected to %s", args.reproject)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mean.rio.to_raster(args.output, driver="GTiff", compress="LZW")
    LOGGER.info("Wrote %s  (CRS %s, size %s)", args.output, mean.rio.crs, dict(mean.sizes))
    LOGGER.info("Point the model's `ndvi_base` at this file.")


if __name__ == "__main__":
    main()
