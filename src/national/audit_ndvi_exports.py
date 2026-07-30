#!/usr/bin/env python3
"""Audit national per-county NDVI exports against the uploaded county AOI.

The default raster statistics are sampled to at most 256 x 256 pixels per file,
which is fast enough for routine completeness checks. Use --full-read before a
final national run if exact valid-pixel fractions and value ranges are required.

Outputs a machine-readable manifest and a short methods/status report.
"""

import argparse
import csv
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUT = BASE_DIR / "results" / "summaries" / "national_ndvi_manifest.csv"
DEFAULT_REPORT = BASE_DIR / "results" / "summaries" / "national_ndvi_audit.md"
NAME_RE = re.compile(r"^(?P<geoid>\d{5})_ndvi\.tif$")


def inspect_raster(item, full_read=False):
    geoid, path, expected = item
    row = {
        "GEOID": geoid,
        "expected_in_aoi": int(expected),
        "file_present": int(path is not None),
        "path": path.name if path else "",
        "readable": 0,
        "crs": "",
        "pixel_size_x": "",
        "pixel_size_y": "",
        "width": "",
        "height": "",
        "sampled_valid_fraction": "",
        "sampled_min": "",
        "sampled_max": "",
        "qa_status": "missing" if path is None else "pending",
        "qa_note": "",
    }
    if path is None:
        row["qa_note"] = "Expected GEOID has no matching export."
        return row
    try:
        import numpy as np
        import rasterio
        from rasterio.enums import Resampling

        with rasterio.open(path) as ds:
            row.update({
                "readable": 1,
                "crs": str(ds.crs or ""),
                "pixel_size_x": abs(ds.transform.a),
                "pixel_size_y": abs(ds.transform.e),
                "width": ds.width,
                "height": ds.height,
            })
            if full_read:
                arr = ds.read(1, masked=True)
            else:
                scale = max(ds.width / 256, ds.height / 256, 1)
                out_h = max(1, round(ds.height / scale))
                out_w = max(1, round(ds.width / scale))
                arr = ds.read(
                    1, out_shape=(out_h, out_w), masked=True,
                    resampling=Resampling.nearest)
            valid = arr.compressed()
            row["sampled_valid_fraction"] = float(valid.size / arr.size)
            if valid.size:
                row["sampled_min"] = float(np.nanmin(valid))
                row["sampled_max"] = float(np.nanmax(valid))
        notes = []
        if row["crs"] != "EPSG:5070":
            notes.append(f"CRS is {row['crs'] or 'missing'}, expected EPSG:5070")
        if not (25 <= float(row["pixel_size_x"]) <= 35 and
                25 <= float(row["pixel_size_y"]) <= 35):
            notes.append("pixel size is outside 25-35 m")
        if row["sampled_valid_fraction"] == 0:
            notes.append("no valid sampled pixels")
        if row["sampled_min"] != "" and (
                float(row["sampled_min"]) < -1.01 or float(row["sampled_max"]) > 1.01):
            notes.append("sampled NDVI is outside [-1, 1]")
        if not expected:
            notes.append("GEOID is not in uploaded AOI")
        row["qa_status"] = "review" if notes else "pass"
        row["qa_note"] = "; ".join(notes)
    except Exception as exc:
        row["qa_status"] = "unreadable"
        row["qa_note"] = str(exc)
    return row


def geoid_column(gdf):
    for name in ("GEOID", "GEOID20"):
        if name in gdf.columns:
            return name
    raise ValueError(f"No county GEOID column in AOI; columns={list(gdf.columns)}")


def main():
    ap = argparse.ArgumentParser(description="Audit national county NDVI exports.")
    ap.add_argument("--regions", type=Path, required=True,
                    help="Exact county AOI uploaded to Earth Engine.")
    ap.add_argument("--ndvi-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--full-read", action="store_true",
                    help="Read every pixel instead of a <=256x256 sample.")
    cli = ap.parse_args()

    import geopandas as gpd

    regions = gpd.read_file(cli.regions)
    col = geoid_column(regions)
    expected = set(regions[col].astype(str).str.zfill(5))
    if len(expected) != len(regions):
        raise SystemExit("AOI contains duplicate county GEOIDs.")

    found = {}
    malformed = []
    for path in sorted(cli.ndvi_dir.glob("*.tif")):
        match = NAME_RE.fullmatch(path.name)
        if not match:
            malformed.append(path.name)
            continue
        geoid = match.group("geoid")
        if geoid in found:
            raise SystemExit(f"Duplicate GEOID export: {geoid}")
        found[geoid] = path

    all_ids = sorted(expected | set(found))
    items = [(geoid, found.get(geoid), geoid in expected) for geoid in all_ids]
    with ThreadPoolExecutor(max_workers=max(1, cli.workers)) as pool:
        rows = list(pool.map(lambda x: inspect_raster(x, cli.full_read), items))

    fields = list(rows[0])
    cli.output.parent.mkdir(parents=True, exist_ok=True)
    with open(cli.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    missing = sorted(expected - set(found))
    unexpected = sorted(set(found) - expected)
    failures = [r for r in rows if r["expected_in_aoi"] and r["qa_status"] != "pass"]
    resolutions = Counter(
        (round(float(r["pixel_size_x"]), 3), round(float(r["pixel_size_y"]), 3))
        for r in rows if r["expected_in_aoi"] and r["readable"])
    resolution_text = ", ".join(
        f"{x:g} x {y:g} m: {count}" for (x, y), count in
        sorted(resolutions.items(), key=lambda item: item[0]))
    method = "full raster read" if cli.full_read else "sampled to <=256 x 256 pixels per raster"
    report = [
        "# National NDVI export audit",
        "",
        f"_Generated {date.today().isoformat()}._",
        "",
        "## Decision",
        "",
        "National completeness is defined by matching the exact county GEOID set in "
        "the Earth Engine upload—not by the number of files in Drive.",
        "",
        "## Result",
        "",
        f"- Expected AOI counties: **{len(expected)}**",
        f"- Correctly named GeoTIFFs: **{len(found)}**",
        f"- Expected files present: **{len(expected & set(found))}**",
        f"- Missing expected GEOIDs: **{len(missing)}**",
        f"- Unexpected GEOIDs outside the AOI: **{len(unexpected)}**",
        f"- Expected rows not passing current QA: **{len(failures)}**",
        f"- Expected-raster resolutions: **{resolution_text or 'none readable'}**",
        f"- Raster-statistics method: **{method}**",
        "",
        f"- Missing: `{', '.join(missing) if missing else 'none'}`",
        f"- Unexpected: `{', '.join(unexpected) if unexpected else 'none'}`",
    ]
    if malformed:
        report += ["", f"- Malformed TIFF names: `{', '.join(malformed)}`"]
    report += [
        "",
        "## Interpretation",
        "",
        "Unexpected files are not automatically invalid; they may come from an older "
        "AOI export. They must be excluded from the current run or the intended study "
        "universe must be revised and re-uploaded consistently. Missing expected files "
        "block a complete national run.",
        "",
        "## To-do",
        "",
        "- Re-export every missing expected GEOID.",
        "- Decide whether unexpected GEOIDs belong in the study universe; do not mix AOI vintages.",
        "- Review every expected row whose `qa_status` is not `pass`.",
        "- Run this audit with `--full-read` before locking the national dataset.",
    ]
    cli.report.write_text("\n".join(report) + "\n")
    print(f"Expected={len(expected)} present={len(expected & set(found))} "
          f"missing={len(missing)} unexpected={len(unexpected)} failures={len(failures)}")
    print(f"Wrote {cli.output}")
    print(f"Wrote {cli.report}")


if __name__ == "__main__":
    main()
