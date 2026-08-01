#!/usr/bin/env python3
"""Run another national scenario using already calibrated central inputs.

This avoids repeating county clipping, reprojection, ACS calibration, and
PLACES extraction for every scenario and radius. It must only be used after a
successful primary `uniform_005` run has built each county's cached inputs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PROJ_NETWORK", "OFF")

import numpy as np
import rasterio
import rioxarray  # noqa: F401
import xarray as xr
import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_city  # noqa: E402


def root_name(scenario: str, radius: float) -> str:
    name = "national" if scenario == "uniform_005" else f"national_{scenario}"
    if radius != 300:
        name += f"_radius_{int(radius)}m"
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geoid", required=True)
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
        required=True,
    )
    parser.add_argument("--search-radius", type=float, default=300)
    parser.add_argument(
        "--cost-file",
        type=Path,
        default=BASE_DIR / "data/urban-mental-health/inputs/health_cost_rate.txt",
    )
    parser.add_argument(
        "--cost-by-region",
        type=Path,
        default=BASE_DIR / "config/cost_by_region.csv",
    )
    cli = parser.parse_args()

    central = (
        BASE_DIR / "data/urban-mental-health/runs/national" / cli.geoid
    )
    required = {
        "aoi_path": central / "inputs/aoi.gpkg",
        "population_raster": central / "inputs/population.tif",
        "baseline_prevalence_vector": central / "inputs/baseline_prevalence.gpkg",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise SystemExit(
            "Primary cached inputs are incomplete; run uniform_005 first: "
            + ", ".join(missing)
        )

    workspace = (
        BASE_DIR / "data/urban-mental-health/runs"
        / root_name(cli.scenario, cli.search_radius)
        / cli.geoid
    )
    inputs = workspace / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    base_path = cli.ndvi_dir / f"{cli.geoid}_ndvi.tif"
    if cli.scenario == "existing_greenness":
        # Historical rasters may declare -9999 nodata while physically storing
        # NaN cells. Write both accounting rasters with finite declared nodata
        # so convolution cannot propagate unmasked non-finite values.
        with rasterio.open(base_path) as source:
            current = source.read(1)
            profile = source.profile.copy()
            valid = np.isfinite(current)
            if source.nodata is not None and np.isfinite(source.nodata):
                valid &= current != source.nodata
        nodata = -9999.0
        profile.update(nodata=nodata, compress="LZW")
        model_base = inputs / "ndvi_zero.tif"
        model_alt = inputs / "ndvi_current_clean.tif"
        with rasterio.open(model_base, "w", **profile) as target:
            target.write(np.where(valid, 0.0, nodata).astype(current.dtype), 1)
        with rasterio.open(model_alt, "w", **profile) as target:
            target.write(np.where(valid, current, nodata).astype(current.dtype), 1)
    else:
        base = rioxarray.open_rasterio(base_path, masked=True).squeeze()
        if cli.scenario == "uniform_005":
            alt = base + run_city.SCENARIO_DELTA
        elif cli.scenario == "proportional_10pct":
            alt = base * (1 + run_city.SCENARIO_PERCENT / 100)
        elif cli.scenario == "greenable_005":
            alt = base + xr.where(
                base < run_city.SCENARIO_TARGET, run_city.SCENARIO_DELTA, 0
            )
        else:
            threshold = float(
                np.nanpercentile(base.values, run_city.SCENARIO_PERCENTILE)
            )
            alt = xr.where(base < threshold, threshold, base)
        alt = xr.where(
            base > run_city.SCENARIO_CAP,
            base,
            alt.clip(max=run_city.SCENARIO_CAP),
        ).where(~base.isnull())
        alt = alt.rio.write_crs(base.rio.crs)
        alt.rio.write_nodata(float("nan"), inplace=True)
        alt.attrs.pop("_FillValue", None)
        model_alt = inputs / "ndvi_alt.tif"
        alt.rio.to_raster(model_alt, driver="GTiff", compress="LZW")
        model_base = base_path

    config = yaml.safe_load((BASE_DIR / "config.yaml").read_text())
    args = {
        "workspace_dir": str(workspace),
        "results_suffix": cli.geoid,
        **{key: str(value) for key, value in required.items()},
        "search_radius": float(cli.search_radius),
        "effect_size": float(config["model"]["effect_size"]),
        "model_option": "ndvi",
        "ndvi_base": str(model_base),
        "ndvi_alt": str(model_alt),
    }
    cost = run_city.resolve_cost(cli)
    if cost is not None:
        args["health_cost_rate"] = cost
    adult_source = central / "adult_pop.txt"
    if adult_source.exists():
        (workspace / "adult_pop.txt").write_text(adult_source.read_text())

    from natcap.invest import urban_mental_health as model

    warnings = model.validate(args)
    for keys, message in warnings:
        run_city.LOGGER.warning("[%s] validate: %s: %s", cli.geoid, keys, message)
    model.MODEL_SPEC.execute(args, create_logfile=True)


if __name__ == "__main__":
    main()
