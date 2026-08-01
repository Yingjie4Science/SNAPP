#!/usr/bin/env python3
"""Build or verify a deterministic SHA-256 manifest of analysis inputs.

The manifest covers checked-in configuration tables plus the local, gitignored
files used by the completed SF and national analyses. Model workspaces and
derived result files are deliberately excluded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "reproducibility/input_checksums.csv"
IGNORED_NAMES = {".DS_Store"}
NDVI_NAME = re.compile(r"^(?P<geoid>\d{5})_ndvi\.tif$")


def locked_geoids(root: Path) -> set[str]:
    with (root / "config/regions.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    geoids = {row["GEOID"].zfill(5) for row in rows}
    if len(rows) != 1167 or len(geoids) != 1167:
        raise ValueError(
            "config/regions.csv must contain exactly 1,167 unique county GEOIDs."
        )
    return geoids


def selected_inputs(root: Path) -> list[Path]:
    """Return the locked analysis inputs in stable repository-relative order."""
    candidates: set[Path] = {root / "config.yaml"}
    candidates.update((root / "config").glob("*.csv"))

    recursive_roots = (
        root / "data/national/counties_gee_upload",
        root / "data/urban-mental-health/raw",
        root / "data/urban-mental-health/inputs",
    )
    for directory in recursive_roots:
        if directory.exists():
            candidates.update(path for path in directory.rglob("*") if path.is_file())

    national = root / "data/national"
    for filename in ("counties_gee_upload.zip", "counties.gpkg", "metro.gpkg"):
        path = national / filename
        if path.is_file():
            candidates.add(path)

    # Select by the locked AOI rather than directory contents. Historical
    # out-of-AOI exports may still exist locally and must never enter the
    # checksum archive or analysis universe silently.
    ndvi_dir = national / "ndvi"
    if ndvi_dir.exists():
        expected = locked_geoids(root)
        found: dict[str, Path] = {}
        for path in ndvi_dir.glob("*.tif"):
            match = NDVI_NAME.fullmatch(path.name)
            if match:
                found[match.group("geoid")] = path
        missing = sorted(expected - found.keys())
        if missing:
            raise FileNotFoundError(
                f"Missing {len(missing)} locked national NDVI inputs: {missing[:20]}"
            )
        unexpected = sorted(found.keys() - expected)
        if unexpected:
            print(
                f"Excluded {len(unexpected)} out-of-AOI NDVI files from the "
                f"locked manifest: {unexpected[:10]}",
                file=sys.stderr,
            )
        candidates.update(found[geoid] for geoid in expected)

    return sorted(
        (
            path
            for path in candidates
            if path.is_file() and path.name not in IGNORED_NAMES
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def current_rows(root: Path) -> list[dict[str, str | int]]:
    rows = []
    paths = selected_inputs(root)
    for number, path in enumerate(paths, 1):
        relative = path.relative_to(root).as_posix()
        if number == 1 or number % 100 == 0 or number == len(paths):
            print(f"[{number}/{len(paths)}] {relative}", file=sys.stderr)
        rows.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return rows


def read_manifest(path: Path) -> list[dict[str, str | int]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"path", "size_bytes", "sha256"}
    if not rows or set(rows[0]) != required:
        raise ValueError(f"{path} must have columns {sorted(required)}")
    return [
        {
            "path": row["path"],
            "size_bytes": int(row["size_bytes"]),
            "sha256": row["sha256"],
        }
        for row in rows
    ]


def write_manifest(path: Path, rows: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=["path", "size_bytes", "sha256"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Repository-shaped data root to hash (default: this checkout).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Recompute local inputs and fail if they differ from the manifest.",
    )
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    source_root = args.source_root.resolve()
    rows = current_rows(source_root)

    if args.verify:
        if not manifest.exists():
            raise SystemExit(f"Manifest does not exist: {manifest}")
        expected = read_manifest(manifest)
        if rows != expected:
            current = {row["path"]: row for row in rows}
            locked = {row["path"]: row for row in expected}
            added = sorted(current.keys() - locked.keys())
            missing = sorted(locked.keys() - current.keys())
            changed = sorted(
                path
                for path in current.keys() & locked.keys()
                if current[path] != locked[path]
            )
            raise SystemExit(
                "Input checksum verification failed: "
                f"added={added[:10]}, missing={missing[:10]}, "
                f"changed={changed[:10]}"
            )
        print(
            f"Verified {len(rows)} input files from {source_root} "
            f"against {manifest}"
        )
        return

    write_manifest(manifest, rows)
    print(
        f"Wrote {len(rows)} input checksums from {source_root} to {manifest}"
    )


if __name__ == "__main__":
    main()
