#!/usr/bin/env python3
"""
Generate per-county NDVI for the national run — the GEE loop feeding run_national.sh.

For each county in the AOI layer (data/national/counties.gpkg), compute the same
Landsat June-Sept 90th-percentile NDVI as ndvi_gee.py (reused directly), clip to
the county, and export <GEOID>_ndvi.tif into --out-dir. run_national.sh /
run_city.py then read those.

Two export modes:
  (default) local download via geemap  — fine for county-sized AOIs at 30 m
  --to-drive                            — batch Export to Google Drive, then
                                          download into --out-dir yourself
                                          (more robust for very large counties)

PREREQUISITES: Earth Engine auth (see ndvi_gee.py); counties.gpkg from
build_metro_counties.py.
REQUIREMENTS  (conda env `snapp`): earthengine-api, geemap, geopandas

USAGE
    python src/inputs/ndvi/ndvi_gee_national.py                      # all counties, 2024
    python src/inputs/ndvi/ndvi_gee_national.py --geoids 06075 36061 # a subset
    python src/inputs/ndvi/ndvi_gee_national.py --to-drive --year 2021
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ndvi_gee  # reuse build_ndvi_collection / yearly_p90 / init_ee / defaults  # noqa: E402

try:
    import ee
    import geemap
    import geopandas as gpd
except ImportError:
    sys.exit("Missing deps. Install: conda install -c conda-forge earthengine-api geemap geopandas")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("ndvi_gee_national")

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_REGIONS = BASE_DIR / "data" / "national" / "counties.gpkg"
DEFAULT_OUT = BASE_DIR / "data" / "national" / "ndvi"
OUT_CRS = "EPSG:5070"          # CONUS Albers, matches the national run
SCALE_M = 30
MIN_TIF_BYTES = 1024           # a real GeoTIFF is far bigger; guards 0-byte/partial files


def is_complete(path: Path) -> bool:
    """True only if the NDVI file exists AND looks like a valid, non-empty raster.

    Guards against a run that died mid-download leaving a truncated/0-byte .tif,
    which the old exists()-only check would have wrongly treated as done.
    """
    if not path.exists() or path.stat().st_size < MIN_TIF_BYTES:
        return False
    try:
        import rasterio
        with rasterio.open(path) as ds:
            return ds.count >= 1 and ds.width > 0 and ds.height > 0
    except ImportError:
        return True            # size check passed and rasterio unavailable
    except Exception:
        return False           # unreadable/corrupt -> redo it


def main():
    ap = argparse.ArgumentParser(description="Per-county Landsat p90 NDVI via GEE.")
    ap.add_argument("--regions", type=Path, default=DEFAULT_REGIONS,
                    help="Counties AOI layer (from build_metro_counties.py).")
    ap.add_argument("--geoids", nargs="*", help="Subset of county GEOIDs (default: all).")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--project", default=ndvi_gee.DEFAULT_EE_PROJECT)
    ap.add_argument("--to-drive", action="store_true",
                    help="Export to Google Drive instead of local download.")
    ap.add_argument("--overwrite", action="store_true", help="Redo counties already present.")
    cli = ap.parse_args()

    if not cli.regions.exists():
        sys.exit(f"Counties layer not found: {cli.regions}. Run build_metro_counties.py first.")
    gdf = gpd.read_file(cli.regions).to_crs("EPSG:4326")   # EE expects lon/lat
    gcol = next((c for c in ("GEOID", "GEOID_PLAC") if c in gdf.columns), None)
    if not gcol:
        sys.exit(f"No GEOID column in {cli.regions} (have {list(gdf.columns)}).")
    if cli.geoids:
        gdf = gdf[gdf[gcol].astype(str).isin([str(g) for g in cli.geoids])]
    if gdf.empty:
        sys.exit("No matching counties to process.")

    ndvi_gee.init_ee(cli.project)
    cli.out_dir.mkdir(parents=True, exist_ok=True)
    n = len(gdf)
    LOGGER.info("Processing %d counties (year %d) -> %s", n, cli.year, cli.out_dir)

    for i, (_, row) in enumerate(gdf.iterrows(), 1):
        geoid = str(row[gcol])
        out = cli.out_dir / f"{geoid}_ndvi.tif"
        if is_complete(out) and not cli.overwrite and not cli.to_drive:
            LOGGER.info("[%d/%d] %s exists (valid) — skip.", i, n, geoid); continue
        if out.exists() and not cli.to_drive:      # present but partial/corrupt -> redo
            LOGGER.warning("[%d/%d] %s exists but is empty/unreadable — re-downloading.",
                           i, n, geoid)
        geom = ee.Geometry(row.geometry.__geo_interface__)
        img = ndvi_gee.yearly_p90(ndvi_gee.build_ndvi_collection(geom), geom, cli.year)
        if cli.to_drive:
            desc = f"NDVI_p90_{cli.year}_{geoid}"
            ee.batch.Export.image.toDrive(
                image=img, description=desc, folder="ndvi_national",
                fileNamePrefix=desc, region=geom, scale=SCALE_M,
                crs=OUT_CRS, maxPixels=int(1e13)).start()
            LOGGER.info("[%d/%d] %s -> Drive job %s", i, n, geoid, desc)
        else:
            geemap.ee_export_image(img, filename=str(out), scale=SCALE_M,
                                   region=geom, crs=OUT_CRS, file_per_band=False)
            LOGGER.info("[%d/%d] %s -> %s", i, n, geoid, out.name)

    if cli.to_drive:
        LOGGER.info("Drive exports started (folder 'ndvi_national'). Download them "
                    "into %s as <GEOID>_ndvi.tif, then run run_national.sh.", cli.out_dir)
    else:
        LOGGER.info("Done. Per-county NDVI in %s — now run run_national.sh.", cli.out_dir)


if __name__ == "__main__":
    main()
