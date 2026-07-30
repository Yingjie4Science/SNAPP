#!/usr/bin/env python3
"""Run one national scenario across all configured counties, resumably.

Each county is an isolated subprocess so a single failure cannot corrupt other
workspaces. Successful counties are skipped on restart unless --force is used.
Per-county logs and a machine-readable completion manifest are retained.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RUN_CITY = BASE_DIR / "src/national/run_city.py"
CACHED_RUN_CITY = BASE_DIR / "src/national/run_city_from_cached_inputs.py"


def scenario_root(scenario: str, radius: float) -> Path:
    name = "national" if scenario == "uniform_005" else f"national_{scenario}"
    if radius != 300:
        name += f"_radius_{int(radius)}m"
    return BASE_DIR / "data/urban-mental-health/runs" / name


def output_complete(root: Path, geoid: str) -> bool:
    output = root / geoid / "output"
    return output.exists() and any(output.glob(f"*sum*{geoid}*.csv"))


def run_one(args: tuple) -> dict:
    (
        python,
        geoid,
        regions,
        prevalence,
        population,
        ndvi_dir,
        scenario,
        radius,
        root,
        force,
        reuse_central_inputs,
    ) = args
    log_dir = root / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if not force and output_complete(root, geoid):
        return {"GEOID": geoid, "status": "skipped_complete", "returncode": 0}
    if reuse_central_inputs:
        command = [
            python,
            str(CACHED_RUN_CITY),
            "--geoid",
            geoid,
            "--ndvi-dir",
            str(ndvi_dir),
            "--scenario",
            scenario,
            "--search-radius",
            str(radius),
        ]
    else:
        command = [
            python,
            str(RUN_CITY),
            "--geoid",
            geoid,
            "--regions",
            str(regions),
            "--prevalence",
            str(prevalence),
            "--population",
            str(population),
            "--ndvi-dir",
            str(ndvi_dir),
            "--scenario",
            scenario,
            "--search-radius",
            str(radius),
        ]
    completed = subprocess.run(
        command,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    (log_dir / f"{geoid}.log").write_text(completed.stdout)
    return {
        "GEOID": geoid,
        "status": "success" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--prevalence", type=Path, required=True)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--ndvi-dir", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=[
            "uniform_005",
            "proportional_10pct",
            "greenable_005",
            "best_potential_p95",
            "existing_greenness",
        ],
        default="uniform_005",
    )
    parser.add_argument("--search-radius", type=float, default=300)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--reuse-central-inputs",
        action="store_true",
        help="Reuse calibrated inputs from the completed uniform_005 run.",
    )
    parser.add_argument("--python", default=sys.executable)
    cli = parser.parse_args()

    regions = cli.regions.resolve()
    import geopandas as gpd

    frame = gpd.read_file(regions)
    geoids = sorted(frame["GEOID"].astype(str).str.zfill(5).unique())
    root = scenario_root(cli.scenario, cli.search_radius)
    root.mkdir(parents=True, exist_ok=True)
    jobs = [
        (
            cli.python,
            geoid,
            regions,
            cli.prevalence.resolve(),
            cli.population.resolve(),
            cli.ndvi_dir.resolve(),
            cli.scenario,
            cli.search_radius,
            root,
            cli.force,
            cli.reuse_central_inputs,
        )
        for geoid in geoids
    ]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=cli.workers) as pool:
        for number, result in enumerate(pool.map(run_one, jobs), 1):
            results.append(result)
            if number % 25 == 0 or number == len(jobs):
                failed = sum(row["status"] == "failed" for row in results)
                print(
                    f"{datetime.now().isoformat(timespec='seconds')} "
                    f"{number}/{len(jobs)} complete; failures={failed}",
                    flush=True,
                )

    manifest = root / "batch_manifest.csv"
    with manifest.open("w", newline="") as target:
        writer = csv.DictWriter(
            target, fieldnames=["GEOID", "status", "returncode"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(results)
    failures = [row["GEOID"] for row in results if row["status"] == "failed"]
    if failures:
        raise SystemExit(
            f"{len(failures)} counties failed; see {root / '_logs'}: "
            + ", ".join(failures[:30])
        )
    print(f"All {len(results)} counties complete; manifest={manifest}")


if __name__ == "__main__":
    main()
