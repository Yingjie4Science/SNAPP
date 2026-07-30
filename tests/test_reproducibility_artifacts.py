"""Validate committed reproducibility metadata without requiring local raw data."""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NDVI_PATH_RE = re.compile(r"^data/national/ndvi/(?P<geoid>\d{5})_ndvi\.tif$")


def test_input_checksum_manifest_is_well_formed_and_uses_locked_aoi():
    path = ROOT / "reproducibility/input_checksums.csv"
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))

    paths = [row["path"] for row in rows]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert "config.yaml" in paths
    assert all(not item.startswith("data/urban-mental-health/runs/") for item in paths)
    assert all(not item.startswith("results/") for item in paths)
    assert all(int(row["size_bytes"]) > 0 for row in rows)
    assert all(SHA256_RE.fullmatch(row["sha256"]) for row in rows)

    expected_geoids = set()
    with (ROOT / "config/regions.csv").open(newline="") as source:
        for row in csv.DictReader(source):
            expected_geoids.add(row["GEOID"].zfill(5))
    locked_ndvi = {
        match.group("geoid")
        for item in paths
        if (match := NDVI_PATH_RE.fullmatch(item))
    }
    assert len(expected_geoids) == 1167
    assert locked_ndvi == expected_geoids


def test_exact_environment_lock_is_explicit_and_credential_free():
    lock = ROOT / "environment-locks/osx-arm64.conda-lock.txt"
    lines = lock.read_text().splitlines()
    assert "# platform: osx-arm64" in lines
    assert "@EXPLICIT" in lines
    urls = [line for line in lines if line.startswith(("http://", "https://"))]
    assert len(urls) > 300
    assert all(line.startswith("https://conda.anaconda.org/conda-forge/") for line in urls)
    assert all("@" not in line.removeprefix("https://") for line in urls)
    assert all("?" not in line for line in urls)
