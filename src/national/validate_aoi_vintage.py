#!/usr/bin/env python3
"""Validate a versioned county-to-CBSA AOI against its source crosswalk.

This validator is intentionally independent of the production AOI paths.  It
checks that the candidate geometry and CSV describe exactly the same whole
counties, and that those counties are exactly the Metropolitan Statistical Area
members in the supplied Census/OMB List 1 crosswalk after applying the declared
study scope.  It also writes a county-level comparison to a legacy AOI.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXCLUDED = ("02", "15", "60", "66", "69", "72", "78")


def read_regions(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"GEOID": str})
    if not {"GEOID", "NAME"}.issubset(frame):
        raise ValueError(f"{path} must contain GEOID and NAME columns")
    frame["GEOID"] = frame["GEOID"].str.zfill(5)
    return frame[["GEOID", "NAME"]].copy()


def crosswalk_members(path: Path, excluded_states: set[str]) -> pd.DataFrame:
    frame = pd.read_excel(path, skiprows=2, dtype=str, engine="openpyxl")
    columns = {str(column).strip().lower(): column for column in frame.columns}
    needed = ("metropolitan/micropolitan statistical area", "fips state code",
              "fips county code", "cbsa code", "cbsa title")
    missing = [name for name in needed if name not in columns]
    if missing:
        raise ValueError(f"{path} is missing crosswalk columns: {missing}")
    metro = columns["metropolitan/micropolitan statistical area"]
    frame = frame[frame[metro].astype(str).str.contains("Metropolitan", na=False)].copy()
    frame["GEOID"] = (frame[columns["fips state code"]].str.zfill(2)
                      + frame[columns["fips county code"]].str.zfill(3))
    frame = frame[~frame["GEOID"].str[:2].isin(excluded_states)]
    frame = frame.rename(columns={columns["cbsa code"]: "metro_id",
                                  columns["cbsa title"]: "metro_name"})
    return frame[["GEOID", "metro_id", "metro_name"]].drop_duplicates("GEOID")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-gpkg", type=Path, required=True)
    parser.add_argument("--candidate-regions", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--legacy-regions", type=Path, default=ROOT / "config/regions.csv")
    parser.add_argument("--report", type=Path, required=True,
                        help="JSON validation report")
    parser.add_argument("--comparison", type=Path, required=True,
                        help="CSV county-level candidate-versus-legacy comparison")
    parser.add_argument("--exclude-states", nargs="*", default=DEFAULT_EXCLUDED,
                        help="Two-digit STATEFP codes excluded from the declared scope")
    parser.add_argument("--include-dc", action="store_true",
                        help="Include DC (STATEFP 11); otherwise it is excluded")
    args = parser.parse_args()

    excluded = set(args.exclude_states)
    if not args.include_dc:
        excluded.add("11")

    candidate = gpd.read_file(args.candidate_gpkg)
    required = {"GEOID", "STATEFP", "metro_id", "metro_name", "geometry"}
    absent = required - set(candidate.columns)
    if absent:
        raise ValueError(f"{args.candidate_gpkg} lacks required columns: {sorted(absent)}")
    candidate["GEOID"] = candidate["GEOID"].astype(str).str.zfill(5)
    candidate["STATEFP"] = candidate["STATEFP"].astype(str).str.zfill(2)
    csv_regions = read_regions(args.candidate_regions)
    expected = crosswalk_members(args.crosswalk, excluded)
    legacy = read_regions(args.legacy_regions)

    candidate_ids = set(candidate["GEOID"])
    csv_ids = set(csv_regions["GEOID"])
    expected_ids = set(expected["GEOID"])
    errors = {
        "candidate_duplicate_geoids": int(candidate["GEOID"].duplicated().sum()),
        "regions_csv_duplicate_geoids": int(csv_regions["GEOID"].duplicated().sum()),
        "candidate_invalid_geometries": int((~candidate.geometry.is_valid).sum()),
        "candidate_missing_from_csv": sorted(candidate_ids - csv_ids),
        "csv_missing_from_candidate": sorted(csv_ids - candidate_ids),
        "candidate_missing_from_crosswalk": sorted(expected_ids - candidate_ids),
        "candidate_not_in_crosswalk": sorted(candidate_ids - expected_ids),
    }
    passed = not any(errors.values())

    candidate_names = candidate[["GEOID", "NAME", "STATEFP", "metro_id", "metro_name"]].copy()
    comparison = (legacy.rename(columns={"NAME": "legacy_name"})
                  .merge(candidate_names.rename(columns={"NAME": "candidate_name"}),
                         on="GEOID", how="outer", indicator=True))
    comparison["change"] = comparison["_merge"].map({
        "left_only": "removed_from_2023_candidate",
        "right_only": "added_in_2023_candidate",
        "both": "shared",
    })
    comparison = comparison.drop(columns="_merge").sort_values("GEOID")
    args.comparison.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.comparison, index=False, quoting=csv.QUOTE_MINIMAL)

    report = {
        "candidate_gpkg": str(args.candidate_gpkg),
        "candidate_regions_csv": str(args.candidate_regions),
        "crosswalk": str(args.crosswalk),
        "legacy_regions_csv": str(args.legacy_regions),
        "scope_excluded_statefp": sorted(excluded),
        "candidate_crs": str(candidate.crs),
        "candidate_counties": len(candidate),
        "candidate_states": int(candidate["STATEFP"].nunique()),
        "expected_crosswalk_counties": len(expected),
        "legacy_counties": len(legacy),
        "shared_with_legacy": int(len(candidate_ids & set(legacy["GEOID"]))),
        "added_vs_legacy": int(len(candidate_ids - set(legacy["GEOID"]))),
        "removed_vs_legacy": int(len(set(legacy["GEOID"]) - candidate_ids)),
        "errors": errors,
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit("AOI validation failed; see report for discrepancies.")


if __name__ == "__main__":
    main()
