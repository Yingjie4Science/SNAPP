#!/usr/bin/env python3
"""Migrate legacy flat SF/national workspaces into grouped run directories.

The migration uses same-filesystem renames, so even a large run archive moves
without copying raster data. It is idempotent and refuses to merge two existing
directories, preventing accidental overwrites.
"""

from __future__ import annotations

import argparse
from pathlib import Path


LEGACY_MOVES = {
    "sf_baseline": "sf/baseline",
    "sf_total_greenness": "sf/existing_greenness",
    "sf_scenarios": "sf/scenarios",
    "sf_sensitivity": "sf/sensitivity",
    "sf_radius_sensitivity": "sf/radius_sensitivity",
    "national_proportional_10pct": "national/proportional_10pct",
    "national_greenable_005": "national/greenable_005",
    "national_best_potential_p95": "national/best_potential_p95",
    "national_existing_greenness": "national/existing_greenness",
    "national_radius_250m": "national/radius_250m",
    "national_radius_500m": "national/radius_500m",
    "national_radius_1000m": "national/radius_1000m",
}


def move(source: Path, destination: Path, dry_run: bool) -> None:
    if not source.exists():
        return
    if destination.exists():
        raise RuntimeError(
            f"Refusing to merge existing directories: {source} and {destination}"
        )
    print(f"{source} -> {destination}")
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)


def migrate(root: Path, dry_run: bool = False) -> None:
    runs = root.resolve() / "data" / "urban-mental-health" / "runs"
    if not runs.exists():
        raise FileNotFoundError(f"Run directory does not exist: {runs}")

    # The legacy primary national workspace itself is named `national`, which
    # is also the new grouping directory. Stage it as a sibling before nesting.
    national = runs / "national"
    new_primary = national / "uniform_005"
    legacy_counties = (
        national.exists()
        and not new_primary.exists()
        and any(path.is_dir() and path.name.isdigit() for path in national.iterdir())
    )
    if legacy_counties:
        staging = runs / ".national_uniform_005_migration"
        if staging.exists():
            raise RuntimeError(f"Migration staging path already exists: {staging}")
        print(f"{national} -> {new_primary}")
        if not dry_run:
            national.rename(staging)
            national.mkdir(parents=True)
            staging.rename(new_primary)

    for legacy_name, grouped_name in LEGACY_MOVES.items():
        move(runs / legacy_name, runs / grouped_name, dry_run)

    print(f"Run layout {'would be migrated' if dry_run else 'is organized'}: {runs}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="SNAPP project/archive root (default: this checkout).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.root, args.dry_run)


if __name__ == "__main__":
    main()
