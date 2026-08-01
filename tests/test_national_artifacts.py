"""Dependency-light validation of committed national evidence artifacts."""

from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SUMMARIES = ROOT / "results/summaries"
EXPECTED_COUNTIES = 1167
EXPECTED_RADIUS_SCENARIOS = {
    "national_summary.csv",
    "national_summary_best_potential_p95.csv",
    "national_summary_greenable_005.csv",
    "national_summary_existing_greenness.csv",
    "national_summary_proportional_10pct.csv",
    "national_summary_uniform_005_radius_250m.csv",
    "national_summary_uniform_005_radius_500m.csv",
    "national_summary_uniform_005_radius_1000m.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def adult_targets() -> dict[str, float]:
    rows = read_csv(CONFIG / "adult_population.csv")
    targets = {row["GEOID"].zfill(5): float(row["population_adult"]) for row in rows}
    assert len(rows) == EXPECTED_COUNTIES
    assert len(targets) == EXPECTED_COUNTIES
    assert all(value > 0 and math.isfinite(value) for value in targets.values())
    return targets


def test_national_ndvi_manifest_is_complete_and_clean():
    targets = adult_targets()
    rows = read_csv(SUMMARIES / "national_ndvi_manifest.csv")
    observed = {row["GEOID"].zfill(5) for row in rows}
    assert len(rows) == EXPECTED_COUNTIES
    assert observed == set(targets)
    for row in rows:
        assert row["expected_in_aoi"] == "1"
        assert row["file_present"] == "1"
        assert row["readable"] == "1"
        assert row["crs"] == "EPSG:5070"
        assert float(row["pixel_size_x"]) == 90
        assert float(row["pixel_size_y"]) == 90
        assert int(row["unmasked_nonfinite_count"]) == 0
        assert row["qa_status"] == "pass"


def test_national_summaries_reconcile_population_and_numeric_outputs():
    targets = adult_targets()
    observed_files = {
        path.name for path in SUMMARIES.glob("national_summary*.csv")
    }
    assert observed_files == EXPECTED_RADIUS_SCENARIOS

    for filename in sorted(EXPECTED_RADIUS_SCENARIOS):
        rows = read_csv(SUMMARIES / filename)
        assert len(rows) == EXPECTED_COUNTIES
        observed = {row["GEOID"].zfill(5) for row in rows}
        assert observed == set(targets)
        assert len(observed) == len(rows)
        for row in rows:
            geoid = row["GEOID"].zfill(5)
            cases = float(row["preventable_cases"])
            cost = float(row["avoided_cost"])
            adults = float(row["adult_population"])
            rate = float(row["preventable_per_1000_adults"])
            assert all(math.isfinite(value) for value in (cases, cost, adults, rate))
            assert cases >= 0
            assert cost >= 0
            assert adults > 0
            assert abs(adults - targets[geoid]) <= 1
            assert math.isclose(cost, cases * 21280, rel_tol=2e-6, abs_tol=2)


def test_committed_final_qa_has_no_failures():
    rows = read_csv(SUMMARIES / "national_final_qa.csv")
    assert len(rows) == 8
    assert all(row["status"] == "pass" for row in rows)
    assert all(int(row["counties"]) == EXPECTED_COUNTIES for row in rows)
    assert all(int(row["missing_geoids"]) == 0 for row in rows)
    assert all(int(row["unexpected_geoids"]) == 0 for row in rows)
    assert all(int(row["duplicate_geoids"]) == 0 for row in rows)
    assert all(int(row["bad_numeric_rows"]) == 0 for row in rows)
    assert all(float(row["max_adult_population_error"]) <= 1 for row in rows)


def test_sf_ndvi_buffer_warning_is_quantified_and_bounded():
    rows = read_csv(SUMMARIES / "sf_ndvi_buffer_audit.csv")
    assert len(rows) == 1
    row = rows[0]
    assert math.isclose(float(row["total_adult_population"]), 716727, abs_tol=1)
    center_coverage = float(row["center_coverage_fraction"])
    full_buffer_coverage = float(row["full_buffer_coverage_fraction"])
    assert 0.999 < full_buffer_coverage < center_coverage < 1
    assert float(row["adult_population_buffer_edge_exposed"]) < 700
