#!/usr/bin/env python3
"""
Build a 10 m annual-mean NDVI GeoTIFF for San Francisco (2024) from Sentinel-2
via CDSE openEO — a higher-resolution alternative to the 300 m Copernicus NDVI.

WHY
    Residential-greenness / mental-health analyses use small (<=300 m) search
    radii, so 10 m Sentinel-2 NDVI is far more appropriate than 300 m pixels.
    openEO computes the NDVI, masks clouds, and averages over the year
    SERVER-SIDE, so you download only the small SF result.

WHAT IT DOES
    load Sentinel-2 L2A (B04, B08, SCL) over SF for 2024
    -> mask clouds/shadows using the SCL band
    -> NDVI = (B08 - B04) / (B08 + B04)
    -> mean over time
    -> download GeoTIFF

REQUIREMENTS
    pip install openeo
    A (free) CDSE account — the first run opens a browser to authenticate.

USAGE
    python src/sf_ndvi/ndvi_sentinel2.py

Then point the model's `ndvi_base` at the output file.
"""

import logging
import sys
from pathlib import Path

try:
    import openeo
except ImportError:
    sys.exit("Missing dep. Install: pip install openeo")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("ndvi_sentinel2")

BASE_DIR = Path(__file__).resolve().parents[3]
OUT = BASE_DIR / "data" / "urban-mental-health" / "inputs" / "sf_ndvi_2024_s2_10m.tif"

# San Francisco bounding box (WGS84). Widen for the whole Bay Area if needed.
SF_EXTENT = {"west": -122.55, "south": 37.70, "east": -122.35, "north": 37.83}
YEAR = "2024"
# Sentinel-2 Scene Classification (SCL) codes to KEEP (drop clouds/shadow/snow):
# 4 = vegetation, 5 = bare soil, 6 = water, 7 = unclassified.
SCL_KEEP = [4, 5, 6, 7]


def main():
    LOGGER.info("Connecting to CDSE openEO (a browser will open to authenticate)...")
    con = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()

    # Load only the bands we need, over SF, for 2024.
    cube = con.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=SF_EXTENT,
        temporal_extent=[f"{YEAR}-01-01", f"{YEAR}-12-31"],
        bands=["B04", "B08", "SCL"],
        max_cloud_cover=70,      # skip very cloudy scenes up front
    )

    # Cloud/shadow mask from SCL: keep only the "good" classes above.
    scl = cube.band("SCL")
    keep = scl == SCL_KEEP[0]
    for code in SCL_KEEP[1:]:
        keep = keep | (scl == code)
    cube = cube.mask(keep.logical_not())    # mask() drops where the mask is True

    # NDVI per observation, then mean over the year (skips masked pixels).
    ndvi = (cube.band("B08") - cube.band("B04")) / (cube.band("B08") + cube.band("B04"))
    ndvi_mean = ndvi.reduce_dimension(dimension="t", reducer="mean")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Submitting batch job (server-side); result -> %s", OUT)
    ndvi_mean.download(OUT, format="GTiff")
    LOGGER.info("Done. Set the model's `ndvi_base` to %s", OUT)


if __name__ == "__main__":
    main()
