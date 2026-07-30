#!/usr/bin/env python3
"""Move county NDVI files outside the final AOI into a separate subfolder."""

import argparse
import re
import shutil
from pathlib import Path

import geopandas as gpd

NAME_RE = re.compile(r"^(\d{5})_ndvi\.tif$")


def main():
    ap = argparse.ArgumentParser(description="Quarantine out-of-AOI NDVI exports.")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--ndvi-dir", type=Path, required=True)
    ap.add_argument("--subfolder", default="_outside_current_aoi")
    cli = ap.parse_args()

    regions = gpd.read_file(cli.regions)
    if "GEOID" not in regions.columns:
        raise SystemExit(f"No GEOID in {cli.regions}.")
    expected = set(regions["GEOID"].astype(str).str.zfill(5))
    destination = cli.ndvi_dir / cli.subfolder
    destination.mkdir(parents=True, exist_ok=True)

    moved = []
    for path in sorted(cli.ndvi_dir.glob("*.tif")):
        match = NAME_RE.fullmatch(path.name)
        if not match or match.group(1) in expected:
            continue
        target = destination / path.name
        if target.exists():
            raise SystemExit(f"Refusing to overwrite existing quarantine file: {target}")
        shutil.move(path, target)
        moved.append(path.name)

    manifest = destination / "MOVED_FROM_ACTIVE_NDVI.txt"
    manifest.write_text(
        "Files outside the current uploaded county AOI.\n"
        f"AOI: {cli.regions}\n"
        f"Moved: {len(moved)}\n\n" + "\n".join(moved) + "\n")
    print(f"Moved {len(moved)} files to {destination}")
    print(f"Wrote {manifest}")


if __name__ == "__main__":
    main()
