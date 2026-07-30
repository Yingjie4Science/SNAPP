#!/usr/bin/env python3
"""Harmonize per-county NDVI rasters onto a common EPSG:5070 grid.

Thirty-metre inputs are aggregated with area averaging. Existing 90 m inputs
are also reprojected to the same 90 m grid origin, avoiding mixed resolution or
misaligned county grids. Source rasters are never modified.
"""

import argparse
import csv
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject


def harmonize_one(source, destination, resolution):
    with rasterio.open(source) as src:
        if str(src.crs) != "EPSG:5070":
            raise ValueError(f"{source.name}: expected EPSG:5070, got {src.crs}")
        left = math.floor(src.bounds.left / resolution) * resolution
        top = math.ceil(src.bounds.top / resolution) * resolution
        width = math.ceil((src.bounds.right - left) / resolution)
        height = math.ceil((top - src.bounds.bottom) / resolution)
        transform = from_origin(left, top, resolution, resolution)
        nodata = -9999.0
        profile = src.profile.copy()
        profile.update(
            driver="GTiff", dtype="float32", count=1, crs="EPSG:5070",
            transform=transform, width=width, height=height, nodata=nodata,
            compress="LZW", tiled=True, blockxsize=256, blockysize=256,
            BIGTIFF="IF_SAFER")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_data = src.read(1).astype("float32", copy=False)
        source_invalid = ~np.isfinite(source_data)
        if src.nodata is not None and np.isfinite(src.nodata):
            source_invalid |= source_data == src.nodata
        source_data = source_data.copy()
        source_data[source_invalid] = nodata
        with rasterio.open(destination, "w", **profile) as dst:
            destination_data = np.full((height, width), nodata, dtype="float32")
            reproject(
                source=source_data,
                destination=destination_data,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=nodata,
                dst_transform=transform,
                dst_crs="EPSG:5070",
                dst_nodata=nodata,
                resampling=Resampling.average,
                num_threads=2)
            destination_data[~np.isfinite(destination_data)] = nodata
            dst.write(destination_data, 1)
        with rasterio.open(destination) as check:
            sample = check.read(
                1,
                out_shape=(min(256, check.height), min(256, check.width)),
                masked=True,
                resampling=Resampling.nearest)
            valid = sample.compressed()
            if not valid.size:
                raise ValueError(f"{source.name}: harmonized raster has no valid pixels")
            if not np.isfinite(valid).all():
                raise ValueError(
                    f"{source.name}: harmonized valid domain contains non-finite pixels"
                )
            if np.nanmin(valid) < -1.01 or np.nanmax(valid) > 1.01:
                raise ValueError(f"{source.name}: harmonized NDVI outside [-1,1]")
        return {
            "file": source.name,
            "source_resolution_m": abs(src.transform.a),
            "target_resolution_m": resolution,
            "target_width": width,
            "target_height": height,
            "sample_min": float(np.nanmin(valid)),
            "sample_max": float(np.nanmax(valid)),
            "status": "pass",
        }


def main():
    ap = argparse.ArgumentParser(description="Harmonize national NDVI resolution.")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--resolution", type=float, default=90)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--manifest", type=Path,
                    help="Default: <output-dir>/harmonization_manifest.csv")
    cli = ap.parse_args()

    regions = gpd.read_file(cli.regions)
    if "GEOID" not in regions.columns:
        raise SystemExit(f"No GEOID in {cli.regions}.")
    expected = sorted(set(regions["GEOID"].astype(str).str.zfill(5)))
    jobs = []
    missing = []
    for geoid in expected:
        source = cli.input_dir / f"{geoid}_ndvi.tif"
        if source.exists():
            jobs.append((source, cli.output_dir / source.name, cli.resolution))
        else:
            missing.append(geoid)
    if missing:
        raise SystemExit(f"Missing {len(missing)} expected source rasters: {missing}")

    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=max(1, cli.workers)) as pool:
        futures = {pool.submit(harmonize_one, *job): job[0].name for job in jobs}
        for index, future in enumerate(as_completed(futures), 1):
            name = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append((name, str(exc)))
            if index % 100 == 0 or index == len(futures):
                print(f"Processed {index}/{len(futures)}; failures={len(errors)}")
    if errors:
        raise SystemExit("Harmonization failures:\n" +
                         "\n".join(f"{name}: {message}" for name, message in errors))

    rows.sort(key=lambda row: row["file"])
    manifest = cli.manifest or cli.output_dir / "harmonization_manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} harmonized rasters to {cli.output_dir}")
    print(f"Wrote {manifest}")


if __name__ == "__main__":
    main()
