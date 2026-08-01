"""Tests for the grouped SF/national run directory layout."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.reproducibility.migrate_run_layout import migrate


def test_legacy_run_layout_migrates_without_data_loss(tmp_path: Path):
    runs = tmp_path / "data/urban-mental-health/runs"
    county = runs / "national" / "06037"
    county.mkdir(parents=True)
    (county / "marker.txt").write_text("national result")
    sf = runs / "sf_baseline"
    sf.mkdir()
    (sf / "marker.txt").write_text("sf result")
    alternative = runs / "national_greenable_005" / "06037"
    alternative.mkdir(parents=True)
    (alternative / "marker.txt").write_text("alternative result")

    migrate(tmp_path)

    assert (
        runs / "national/uniform_005/06037/marker.txt"
    ).read_text() == "national result"
    assert (runs / "sf/baseline/marker.txt").read_text() == "sf result"
    assert (
        runs / "national/greenable_005/06037/marker.txt"
    ).read_text() == "alternative result"

    # Re-running the migration is a no-op rather than an overwrite.
    migrate(tmp_path)
