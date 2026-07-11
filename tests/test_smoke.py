"""
Lightweight smoke tests for the SNAPP pipeline. Run: `pytest` from the repo root.

These test dependency-light logic (cost math, config integrity) so they pass in
CI without the heavy GDAL/natcap stack. Heavy modules are import-skipped if their
deps aren't installed.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "src" / "inputs"


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- health cost math (needs openpyxl, which is light) ----
def test_cost_anchors_and_pooled():
    pytest.importorskip("openpyxl")
    ehc = _load(INPUTS / "estimate_health_cost.py")
    # Greenberg 2018 anchor -> ~ $22.6k in 2024 USD
    g18 = ehc.anchor_per_case("greenberg2018", 2024)
    assert 22000 < g18 < 23200
    # Greenberg 2019 anchor -> ~ $19.9k
    g19 = ehc.anchor_per_case("greenberg2019", 2024)
    assert 19000 < g19 < 20800
    # pooled component total -> ~ $21.3k (shares sum ~1.002)
    comps = ehc.societal_components("pooled", 2024, 1.0)
    total = sum(comps.values())
    assert 20500 < total < 21800
    # wage factor scales only workplace + suicide
    comps_sf = ehc.societal_components("pooled", 2024, 1.15)
    assert comps_sf["direct_comorbid"] == pytest.approx(comps["direct_comorbid"])
    assert comps_sf["workplace_productivity"] > comps["workplace_productivity"]


def test_cpi_monotonic():
    pytest.importorskip("openpyxl")
    ehc = _load(INPUTS / "estimate_health_cost.py")
    years = sorted(ehc.CPI_U)
    vals = [ehc.CPI_U[y] for y in years]
    assert vals == sorted(vals)  # CPI increases over time


# ---- config integrity ----
def test_config_has_required_keys():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    assert cfg["model"]["effect_size"] == 0.93
    assert cfg["model"]["search_radius_m"] == 300
    assert 0 < cfg["population"]["adult_fraction"] <= 1.0
    for k in ("low_usd", "central_usd", "high_usd"):
        assert cfg["cost"][k] > 0
    assert cfg["cost"]["low_usd"] < cfg["cost"]["central_usd"] < cfg["cost"]["high_usd"]


# ---- NDVI scenario capping (needs rioxarray/xarray; skip if absent) ----
def test_ndvi_scenario_caps():
    pytest.importorskip("xarray")
    pytest.importorskip("rioxarray")
    import numpy as np
    import xarray as xr
    base = xr.DataArray(np.array([[0.10, 0.88, np.nan]]), dims=("y", "x"))
    alt = (base + 0.05).clip(max=0.90).where(~base.isnull())
    vals = alt.values.ravel()
    assert vals[0] == pytest.approx(0.15)   # normal add
    assert vals[1] == pytest.approx(0.90)   # capped (0.93 -> 0.90)
    assert np.isnan(vals[2])                # nodata preserved
