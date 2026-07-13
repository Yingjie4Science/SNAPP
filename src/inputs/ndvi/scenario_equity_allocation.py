#!/usr/bin/env python3
"""Create matched-budget feasible greening scenarios with transparent priorities.

All three alternatives allocate the same fraction of the feasible NLCD-based
NDVI potential.  They differ only in the tract priority score supplied by
advanced_equity_analysis.py:
  health   = modeled preventable cases per unit of feasible NDVI increment
  equity   = benefit rate + SVI + baseline-greenness deficit
  balanced = equal blend of health and equity scores
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

import numpy as np

try:
    import geopandas as gpd
    import rioxarray  # noqa: F401
    import xarray as xr
    from rasterio.features import rasterize
except ImportError:
    sys.exit("Requires geopandas, rioxarray, rasterio, xarray, and numpy.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("scenario_equity_allocation")

BASE = Path(__file__).resolve().parents[3]
UMH = BASE / "data" / "urban-mental-health"
INPUTS = UMH / "inputs"
RAW = UMH / "raw" / "nlcd"
TRACTS = BASE / "results" / "summaries" / "advanced_equity_tracts.csv"
OUT_BUDGET = BASE / "results" / "summaries" / "equity_allocation_budget.csv"


def read_scores(path: Path):
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            try:
                out[str(row["GEOID"]).zfill(11)] = {
                    "health": float(row["health_score"]),
                    "equity": float(row["equity_score"]),
                    "balanced": float(row["balanced_score"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
    return out


def allocate(potential, candidate, scores, budget):
    """Greedily spend a fixed NDVI-increment budget on highest-score cells."""
    out = np.zeros_like(potential, dtype="float32")
    flat = np.flatnonzero(candidate & np.isfinite(scores) & (potential > 0))
    order = flat[np.lexsort((flat, -scores.flat[flat]))]
    remaining = float(budget)
    for idx in order:
        if remaining <= 1e-10:
            break
        add = min(float(potential.flat[idx]), remaining)
        out.flat[idx] = add
        remaining -= add
    return out, remaining


def main():
    ap = argparse.ArgumentParser(description="Generate matched-budget equity allocation scenarios.")
    ap.add_argument("--scores", type=Path, default=TRACTS)
    ap.add_argument("--ndvi-base", type=Path, default=INPUTS / "ndvi_base.tif")
    ap.add_argument("--lulc", type=Path, default=RAW / "nlcd_landcover.tif")
    ap.add_argument("--aoi", type=Path, default=INPUTS / "aoi.gpkg")
    ap.add_argument("--budget-fraction", type=float, default=0.50,
                    help="Share of full feasible NDVI-increment potential allocated to each scenario.")
    ap.add_argument("--target", type=float, default=0.65)
    ap.add_argument("--delta", type=float, default=0.15)
    ap.add_argument("--cap", type=float, default=0.90)
    cli = ap.parse_args()
    if not 0 < cli.budget_fraction <= 1:
        sys.exit("--budget-fraction must be in (0, 1].")
    for path in (cli.scores, cli.ndvi_base, cli.lulc, cli.aoi):
        if not path.exists():
            sys.exit(f"Missing input: {path}")
    score_by_geoid = read_scores(cli.scores)
    base = rioxarray.open_rasterio(cli.ndvi_base, masked=True).squeeze()
    lulc = rioxarray.open_rasterio(cli.lulc, masked=True).squeeze().rio.reproject_match(base, resampling=0)
    aoi = gpd.read_file(cli.aoi).to_crs(base.rio.crs).copy()
    aoi["GEOID"] = aoi["GEOID"].astype(str).str.zfill(11)
    aoi["_id"] = range(1, len(aoi) + 1)
    ids = rasterize(((geom, ident) for geom, ident in zip(aoi.geometry, aoi._id)),
                    out_shape=(base.rio.height, base.rio.width), transform=base.rio.transform(),
                    fill=0, dtype="int32")
    arr, lulc_arr = base.values.astype("float32"), lulc.values
    eligible = np.isin(lulc_arr, [21, 22, 31]) & np.isfinite(arr) & (ids > 0)
    potential = np.where(eligible, np.maximum(0, np.minimum(arr + cli.delta, cli.target) - arr), 0).astype("float32")
    total_potential = float(potential.sum())
    budget = total_potential * cli.budget_fraction
    if budget <= 0:
        sys.exit("No feasible NDVI increment potential found.")
    OUT_BUDGET.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for score_name, filename in [("health", "ndvi_scenario_health_priority.tif"),
                                 ("equity", "ndvi_scenario_equity_priority.tif"),
                                 ("balanced", "ndvi_scenario_balanced_priority.tif")]:
        score_arr = np.full(arr.shape, np.nan, dtype="float32")
        for geoid, ident in zip(aoi.GEOID, aoi._id):
            score_arr[ids == ident] = score_by_geoid.get(geoid, {}).get(score_name, np.nan)
        addition, unspent = allocate(potential, eligible, score_arr, budget)
        alt = np.where(np.isfinite(arr), np.minimum(arr + addition, cli.cap), np.nan).astype("float32")
        da = base.copy(data=alt).rio.write_crs(base.rio.crs)
        da.rio.write_nodata(float("nan"), inplace=True)
        da.attrs.pop("_FillValue", None)
        output = INPUTS / filename
        da.rio.to_raster(output, driver="GTiff", compress="LZW")
        records.append({"scenario": f"{score_name}_priority_feasible", "ndvi_alt": filename,
                        "budget_fraction": cli.budget_fraction, "ndvi_increment_budget": budget,
                        "ndvi_increment_allocated": float(addition.sum()), "unspent": unspent,
                        "eligible_pixels": int(eligible.sum())})
        LOGGER.info("Wrote %s (%s priority, %.1f%% feasible-potential budget)", output, score_name,
                    100 * cli.budget_fraction)
    with open(OUT_BUDGET, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(records[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(records)


if __name__ == "__main__":
    main()
