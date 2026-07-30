#!/usr/bin/env python3
"""Fail-closed QA for completed national scenario and radius outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
SUMMARIES = BASE_DIR / "results/summaries"
EXPECTED = 1167


def summary_path(scenario: str, radius: int) -> Path:
    if scenario == "uniform_005" and radius == 300:
        return SUMMARIES / "national_summary.csv"
    suffix = f"_{scenario}"
    if radius != 300:
        suffix += f"_radius_{radius}m"
    return SUMMARIES / f"national_summary{suffix}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario to validate; repeatable.",
    )
    parser.add_argument(
        "--radius", action="append", type=int, default=[],
        help="Uniform-scenario radius to validate; repeatable.",
    )
    cli = parser.parse_args()
    scenarios = cli.scenario or [
        "uniform_005",
        "proportional_10pct",
        "greenable_005",
        "best_potential_p95",
    ]
    radii = cli.radius or [250, 300, 500, 1000]

    adults = pd.read_csv(
        BASE_DIR / "config/adult_population.csv", dtype={"GEOID": str}
    )
    adults["GEOID"] = adults["GEOID"].str.zfill(5)
    expected_ids = set(adults["GEOID"])
    if len(expected_ids) != EXPECTED:
        raise SystemExit(f"Expected {EXPECTED} adult targets, found {len(expected_ids)}.")

    checks = []
    targets = [(scenario, 300) for scenario in scenarios]
    targets += [
        ("uniform_005", radius) for radius in radii if radius != 300
    ]
    for scenario, radius in targets:
        path = summary_path(scenario, radius)
        if not path.exists():
            checks.append({
                "scenario": scenario, "radius_m": radius, "status": "missing",
                "counties": 0, "missing_geoids": EXPECTED,
            })
            continue
        frame = pd.read_csv(path, dtype={"GEOID": str})
        frame["GEOID"] = frame["GEOID"].str.zfill(5)
        ids = set(frame["GEOID"])
        numeric = frame[[
            "preventable_cases", "avoided_cost", "adult_population",
            "preventable_per_1000_adults",
        ]].apply(pd.to_numeric, errors="coerce")
        duplicates = int(frame["GEOID"].duplicated().sum())
        bad_numeric = int((~np.isfinite(numeric.to_numpy())).any(axis=1).sum())
        nonpositive_population = int(numeric["adult_population"].le(0).sum())
        negative_cases = int(numeric["preventable_cases"].lt(-1e-3).sum())
        joined = frame[["GEOID", "adult_population"]].merge(
            adults[["GEOID", "population_adult"]],
            on="GEOID",
            how="outer",
            validate="one_to_one",
        )
        max_population_error = float(
            (
                pd.to_numeric(joined["adult_population"], errors="coerce")
                - joined["population_adult"]
            ).abs().max()
        )
        missing = len(expected_ids - ids)
        unexpected = len(ids - expected_ids)
        passed = (
            len(frame) == EXPECTED
            and not missing
            and not unexpected
            and not duplicates
            and not bad_numeric
            and not nonpositive_population
            and not negative_cases
            and max_population_error <= 1
        )
        checks.append({
            "scenario": scenario,
            "radius_m": radius,
            "status": "pass" if passed else "fail",
            "counties": len(frame),
            "missing_geoids": missing,
            "unexpected_geoids": unexpected,
            "duplicate_geoids": duplicates,
            "bad_numeric_rows": bad_numeric,
            "nonpositive_population_rows": nonpositive_population,
            "negative_case_rows": negative_cases,
            "max_adult_population_error": max_population_error,
            "total_adult_population": numeric["adult_population"].sum(),
            "total_preventable_cases": numeric["preventable_cases"].sum(),
            "total_avoided_cost": numeric["avoided_cost"].sum(),
        })

    table = pd.DataFrame(checks)
    table.to_csv(SUMMARIES / "national_final_qa.csv", index=False)
    lines = [
        "# National final QA",
        "",
        "| Scenario | Radius | Status | Counties | Missing | Bad numeric | "
        "Max adult-pop error | Cases/year |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in checks:
        lines.append(
            f"| {row['scenario']} | {row['radius_m']} | {row['status']} | "
            f"{row['counties']} | {row['missing_geoids']} | "
            f"{row.get('bad_numeric_rows', '—')} | "
            f"{row.get('max_adult_population_error', float('nan')):.1f} | "
            f"{row.get('total_preventable_cases', float('nan')):,.0f} |"
        )
    lines += [
        "",
        "A passing row requires exactly 1,167 unique expected counties, finite "
        "case/cost/rate values, non-negative cases, positive adult population, "
        "and county population totals within one person of ACS 2023 targets.",
    ]
    (SUMMARIES / "national_final_qa.md").write_text("\n".join(lines) + "\n")
    failed = table.loc[table["status"].ne("pass"), ["scenario", "radius_m", "status"]]
    if not failed.empty:
        raise SystemExit("National QA failed:\n" + failed.to_string(index=False))


if __name__ == "__main__":
    main()
