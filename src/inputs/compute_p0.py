#!/usr/bin/env python3
"""
Derive the OR->RR baseline risk p0 from the model's own prevalence + population,
then refresh the converted risk ratios in config.yaml.

Why
    The effect size is a published ODDS RATIO (Liu 2023) that we convert to the
    RISK RATIO InVEST expects, via RR = OR / (1 - p0 + p0*OR) (Zhang & Yu 1998).
    p0 is the baseline depression risk. The most defensible, self-consistent
    choice is the POPULATION-WEIGHTED MEAN of the SAME CDC PLACES prevalence layer
    the model uses (same outcome definition, same geography) rather than an
    external number. This script computes that p0 and rewrites config.yaml's
    effect_size / _low / _high (and baseline_risk_p0) accordingly. See
    docs/effect_size.md.

Method
    Rasterize the prevalence polygons' `risk_rate` onto the population grid,
    then p0 = sum(pop_i * prev_i) / sum(pop_i) over tracts (fast, no per-polygon
    loop). --simple-mean uses an unweighted tract mean instead (instant; p0 is
    insensitive, so this is an acceptable fallback).

REQUIREMENTS (conda env `snapp`): geopandas, rioxarray, rasterio, numpy, pyyaml
USAGE
    python src/inputs/compute_p0.py                      # SF inputs, pop-weighted, updates config
    python src/inputs/compute_p0.py --prevalence <gpkg> --population <tif>
    python src/inputs/compute_p0.py --simple-mean --no-write   # just print
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("compute_p0")

BASE_DIR = Path(__file__).resolve().parents[2]
INPUTS = BASE_DIR / "data" / "urban-mental-health" / "inputs"
CONFIG = BASE_DIR / "config.yaml"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from effect_size import or_to_rr  # noqa: E402


def population_weighted_p0(prev_path: Path, pop_path: Path, simple_mean: bool) -> float:
    import geopandas as gpd
    import numpy as np
    import rioxarray  # noqa: F401

    gdf = gpd.read_file(prev_path)
    if "risk_rate" not in gdf.columns:
        sys.exit(f"'risk_rate' not in {prev_path} (have {list(gdf.columns)}).")
    gdf = gdf[gdf["risk_rate"].notna()].copy()

    if simple_mean:
        return float(gdf["risk_rate"].mean())

    import rasterio
    from rasterio.features import rasterize

    pop = rioxarray.open_rasterio(pop_path, masked=True).squeeze()
    gdf = gdf.to_crs(pop.rio.crs).reset_index(drop=True)
    gdf["_id"] = range(1, len(gdf) + 1)                 # 0 = background
    transform = pop.rio.transform()
    shape = (pop.rio.height, pop.rio.width)
    id_arr = rasterize(((geom, i) for geom, i in zip(gdf.geometry, gdf["_id"])),
                       out_shape=shape, transform=transform, fill=0, dtype="int32")
    pop_flat = np.asarray(pop.values, dtype="float64").ravel()
    id_flat = id_arr.ravel()
    valid = np.isfinite(pop_flat) & (pop_flat > 0) & (id_flat > 0)
    pop_by_tract = np.bincount(id_flat[valid], weights=pop_flat[valid],
                               minlength=len(gdf) + 1)[1:]
    prev = gdf.sort_values("_id")["risk_rate"].to_numpy(dtype="float64")
    denom = pop_by_tract.sum()
    if denom <= 0:
        LOGGER.warning("No population overlapped tracts; falling back to simple mean.")
        return float(gdf["risk_rate"].mean())
    return float((pop_by_tract * prev).sum() / denom)


def update_config(p0: float, rr_c: float, rr_lo: float, rr_hi: float,
                  or_c: float, or_lo: float, or_hi: float):
    text = CONFIG.read_text()

    def repl(key, line):
        nonlocal text
        text = re.sub(rf"(?m)^\s*{key}:.*$", line, text)

    repl("effect_size",
         f"  effect_size: {rr_c:.3f}          # RR central (OR {or_c} at p0={p0:.3f}); derived by compute_p0.py")
    repl("effect_size_low",
         f"  effect_size_low: {rr_lo:.3f}      # RR bound (OR {or_lo} = more protective)")
    repl("effect_size_high",
         f"  effect_size_high: {rr_hi:.3f}     # RR bound (OR {or_hi} = least protective)")
    repl("baseline_risk_p0",
         f"  baseline_risk_p0: {p0:.3f}      # population-weighted PLACES prevalence (compute_p0.py)")
    CONFIG.write_text(text)
    LOGGER.info("Updated config.yaml: p0=%.3f -> effect_size RR %.3f (%.3f-%.3f).",
                p0, rr_c, rr_lo, rr_hi)


def main():
    ap = argparse.ArgumentParser(description="Derive p0 from data and refresh config RRs.")
    ap.add_argument("--prevalence", type=Path, default=INPUTS / "baseline_prevalence.gpkg")
    ap.add_argument("--population", type=Path, default=INPUTS / "population.tif")
    ap.add_argument("--simple-mean", action="store_true",
                    help="Unweighted tract mean instead of population-weighted.")
    ap.add_argument("--no-write", action="store_true", help="Print only; don't edit config.yaml.")
    cli = ap.parse_args()

    for p in (cli.prevalence, cli.population):
        if not p.exists():
            sys.exit(f"Missing input: {p}. Build model inputs first.")

    p0 = population_weighted_p0(cli.prevalence, cli.population, cli.simple_mean)

    # Read published ORs from config.
    try:
        import yaml
        m = (yaml.safe_load(CONFIG.read_text()) or {}).get("model", {})
    except Exception:
        m = {}
    or_c = float(m.get("effect_size_or", 0.931))
    or_lo = float(m.get("effect_size_or_low", 0.887))
    or_hi = float(m.get("effect_size_or_high", 0.977))
    rr_c, rr_lo, rr_hi = (or_to_rr(or_c, p0), or_to_rr(or_lo, p0), or_to_rr(or_hi, p0))

    LOGGER.info("p0 (%s) = %.4f", "simple mean" if cli.simple_mean else "population-weighted", p0)
    LOGGER.info("RR central %.4f  low %.4f  high %.4f", rr_c, rr_lo, rr_hi)

    # p0 sensitivity, so the choice is visibly robust.
    LOGGER.info("p0 sensitivity (central OR %.3f):", or_c)
    for p in (0.10, 0.15, 0.20, 0.25, 0.30):
        LOGGER.info("   p0=%.2f -> RR %.4f", p, or_to_rr(or_c, p))

    if not cli.no_write:
        update_config(p0, rr_c, rr_lo, rr_hi, or_c, or_lo, or_hi)
    else:
        LOGGER.info("--no-write: config.yaml unchanged.")


if __name__ == "__main__":
    main()
