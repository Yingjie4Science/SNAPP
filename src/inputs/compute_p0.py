#!/usr/bin/env python3
"""
Derive the OR->RR baseline risk p0 from the model's own prevalence + population,
then refresh the converted risk ratios in config.yaml.

Why
    The effect size is a published ODDS RATIO (Liu 2023) that we convert to the
    RISK RATIO InVEST expects, via RR = OR / (1 - p0 + p0*OR) (Zhang & Yu 1998).
    p0 is the baseline depression risk in a reference / least-green population.
    For the U.S. primary analysis, the planned estimate is the population-weighted
    CDC PLACES prevalence among tracts in the lowest population-weighted NDVI
    quantile. The overall population-weighted prevalence remains available as an
    explicitly INTERIM fallback until the national NDVI set is complete.

Method
    Rasterize prevalence polygons onto the population grid and aggregate adult
    population by tract. For --reference lowest-ndvi-quantile, also align NDVI
    to the population grid, calculate population-weighted mean NDVI by tract,
    find the requested population-weighted NDVI threshold, and calculate p0
    among tracts below that threshold.

REQUIREMENTS (conda env `snapp`): geopandas, rioxarray, rasterio, numpy, pyyaml
USAGE
    python src/inputs/compute_p0.py                      # interim overall mean, updates config
    python src/inputs/compute_p0.py --reference lowest-ndvi-quantile --quantile 0.25
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


def _weighted_quantile(values, weights, quantile):
    import numpy as np

    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    if cumulative[-1] <= 0:
        raise ValueError("Weighted quantile has zero total weight.")
    return float(values[np.searchsorted(cumulative, quantile * cumulative[-1], side="left")])


def population_weighted_p0(prev_path: Path, pop_path: Path, simple_mean: bool,
                           reference: str = "overall", ndvi_path: Path | None = None,
                           quantile: float = 0.25) -> tuple[float, dict]:
    import geopandas as gpd
    import numpy as np
    import rioxarray  # noqa: F401

    gdf = gpd.read_file(prev_path)
    if "risk_rate" not in gdf.columns:
        sys.exit(f"'risk_rate' not in {prev_path} (have {list(gdf.columns)}).")
    gdf = gdf[gdf["risk_rate"].notna()].copy()

    if simple_mean:
        if reference != "overall":
            sys.exit("--simple-mean is only available with --reference overall.")
        return float(gdf["risk_rate"].mean()), {
            "method": "unweighted_tract_mean_places",
            "matched_tracts": len(gdf),
        }

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
        return float(gdf["risk_rate"].mean()), {
            "method": "unweighted_tract_mean_fallback",
            "matched_tracts": len(gdf),
        }

    overall = float((pop_by_tract * prev).sum() / denom)
    if reference == "overall":
        return overall, {
            "method": "aoi_overall_population_weighted_places_interim",
            "matched_tracts": int((pop_by_tract > 0).sum()),
            "adult_population": float(denom),
        }

    if ndvi_path is None or not ndvi_path.exists():
        sys.exit("--reference lowest-ndvi-quantile requires an existing --ndvi raster.")
    if not 0 < quantile < 1:
        sys.exit("--quantile must be between 0 and 1.")

    from rasterio.enums import Resampling

    ndvi = rioxarray.open_rasterio(ndvi_path, masked=True).squeeze()
    ndvi = ndvi.rio.reproject_match(pop, resampling=Resampling.bilinear)
    ndvi_flat = np.asarray(ndvi.values, dtype="float64").ravel()
    valid_ndvi = valid & np.isfinite(ndvi_flat)
    pop_ndvi = np.bincount(id_flat[valid_ndvi], weights=pop_flat[valid_ndvi],
                           minlength=len(gdf) + 1)[1:]
    ndvi_num = np.bincount(
        id_flat[valid_ndvi],
        weights=pop_flat[valid_ndvi] * ndvi_flat[valid_ndvi],
        minlength=len(gdf) + 1)[1:]
    tract_ndvi = np.divide(ndvi_num, pop_ndvi, out=np.full(len(gdf), np.nan),
                           where=pop_ndvi > 0)
    eligible = np.isfinite(tract_ndvi) & (pop_ndvi > 0)
    threshold = _weighted_quantile(tract_ndvi[eligible], pop_ndvi[eligible], quantile)
    selected = eligible & (tract_ndvi <= threshold)
    selected_pop = float(pop_ndvi[selected].sum())
    if selected_pop <= 0:
        sys.exit("No populated tracts were selected for the low-NDVI reference group.")
    p0 = float((pop_ndvi[selected] * prev[selected]).sum() / selected_pop)
    return p0, {
        "method": f"lowest_population_weighted_ndvi_quantile_{quantile:g}",
        "quantile": quantile,
        "ndvi_threshold": threshold,
        "matched_tracts": int(eligible.sum()),
        "selected_tracts": int(selected.sum()),
        "adult_population": float(pop_ndvi[eligible].sum()),
        "selected_adult_population": selected_pop,
        "ndvi_population_coverage": float(pop_ndvi[eligible].sum() / denom),
        "overall_population_weighted_p0": overall,
    }


def update_config(p0: float, rr_c: float, rr_lo: float, rr_hi: float,
                  or_c: float, or_lo: float, or_hi: float, method: str):
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
         f"  baseline_risk_p0: {p0:.3f}")
    repl("baseline_risk_p0_method",
         f'  baseline_risk_p0_method: "{method}"')
    CONFIG.write_text(text)
    LOGGER.info("Updated config.yaml: p0=%.3f -> effect_size RR %.3f (%.3f-%.3f).",
                p0, rr_c, rr_lo, rr_hi)


def main():
    ap = argparse.ArgumentParser(description="Derive p0 from data and refresh config RRs.")
    ap.add_argument("--prevalence", type=Path, default=INPUTS / "baseline_prevalence.gpkg")
    ap.add_argument("--population", type=Path, default=INPUTS / "population.tif")
    ap.add_argument("--ndvi", type=Path, default=INPUTS / "ndvi_base.tif",
                    help="Baseline NDVI; required for the low-NDVI reference method.")
    ap.add_argument("--reference", choices=["overall", "lowest-ndvi-quantile"],
                    default="overall",
                    help="Reference-risk method. 'overall' is an interim fallback; "
                         "the U.S. primary method is lowest-ndvi-quantile.")
    ap.add_argument("--quantile", type=float, default=0.25,
                    help="Population-weighted low-NDVI fraction (default 0.25).")
    ap.add_argument("--simple-mean", action="store_true",
                    help="Unweighted tract mean instead of population-weighted.")
    ap.add_argument("--no-write", action="store_true", help="Print only; don't edit config.yaml.")
    cli = ap.parse_args()

    for p in (cli.prevalence, cli.population):
        if not p.exists():
            sys.exit(f"Missing input: {p}. Build model inputs first.")

    p0, details = population_weighted_p0(
        cli.prevalence, cli.population, cli.simple_mean, cli.reference,
        cli.ndvi, cli.quantile)

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

    LOGGER.info("p0 method=%s = %.4f", details["method"], p0)
    for key, value in details.items():
        if key != "method":
            LOGGER.info("  %s=%s", key, value)
    LOGGER.info("RR central %.4f  low %.4f  high %.4f", rr_c, rr_lo, rr_hi)

    # p0 sensitivity, so the choice is visibly robust.
    LOGGER.info("p0 sensitivity (central OR %.3f):", or_c)
    for p in (0.10, 0.15, 0.20, 0.25, 0.30):
        LOGGER.info("   p0=%.2f -> RR %.4f", p, or_to_rr(or_c, p))

    if not cli.no_write:
        update_config(p0, rr_c, rr_lo, rr_hi, or_c, or_lo, or_hi,
                      details["method"])
    else:
        LOGGER.info("--no-write: config.yaml unchanged.")


if __name__ == "__main__":
    main()
