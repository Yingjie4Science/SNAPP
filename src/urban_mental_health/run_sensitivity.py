#!/usr/bin/env python3
"""
Sensitivity analysis for the Urban Mental Health model (SF).

Varies the two key assumptions and reports how the results move:
  - effect_size  : RISK RATIOs 0.908 (more protective) / 0.944 (central) / 0.982,
                   converted OR->RR from Liu 2023 (see docs/effect_size.md)
  - health_cost_rate : $17,000 (low) / $21,280 (pooled central) / $23,000 (high)

Only effect_size changes the number of preventable CASES, so the model is run
once per effect_size (3 runs). preventable COST scales linearly with the cost
rate, so the cost bands are computed analytically (cases x each cost) — no need
to re-run the model for every cost. Results go to a summary CSV.

REQUIREMENTS  (conda env `snapp`): natcap.invest, rasterio, numpy
USAGE
    python src/urban_mental_health/run_sensitivity.py
Outputs:
    data/urban-mental-health/runs/sf_sensitivity/<label>/   (per-run workspaces)
    data/urban-mental-health/runs/sf_sensitivity/sensitivity_summary.csv
"""

import csv
import glob
import logging
import sys
from pathlib import Path

# Import the SF model config (build_args, load_model, paths) from the sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("run_sensitivity")

# Effect sizes are RISK RATIOs (converted OR->RR; see config.yaml + docs/effect_size.md).
# Pulled from config so there's one source of truth; falls back to the converted defaults.
_M = run_model._MODEL
EFFECT_SIZES = {
    f"es_low_rr_{_M.get('effect_size_low', 0.908)}": float(_M.get("effect_size_low", 0.908)),
    f"es_central_rr_{_M.get('effect_size', 0.944)}": float(_M.get("effect_size", 0.944)),
    f"es_high_rr_{_M.get('effect_size_high', 0.982)}": float(_M.get("effect_size_high", 0.982)),
}
COST_RATES = {"cost_low_17000": 17000.0, "cost_central_21280": 21280.0, "cost_high_23000": 23000.0}

WS_ROOT = run_model.RUNS / "sf_sensitivity"                 # runs (gitignored)
SUMMARY_CSV = run_model.RESULTS_SUMMARIES / "sensitivity_summary.csv"  # committed


def total_preventable_cases(workspace: Path, suffix: str) -> float:
    """Sum the preventable_cases output raster for one run (people)."""
    import numpy as np
    import rasterio

    out = workspace / "output"
    cands = (sorted(out.glob(f"*preventable_cases*{suffix}*.tif"))
             or sorted(out.glob("*preventable_cases*.tif")))
    if not cands:
        LOGGER.warning("No preventable_cases raster found in %s", out)
        return float("nan")
    with rasterio.open(cands[0]) as ds:
        arr = ds.read(1, masked=True)
    return float(np.nansum(arr.filled(0.0)))


def main():
    WS_ROOT.mkdir(parents=True, exist_ok=True)
    model = run_model.load_model()
    base = run_model.build_args()          # baseline SF args (ndvi, aoi, population, ...)

    rows = []
    for label, es in EFFECT_SIZES.items():
        ws = WS_ROOT / label
        ws.mkdir(parents=True, exist_ok=True)
        args = dict(base)
        args["workspace_dir"] = str(ws)
        args["results_suffix"] = label
        args["effect_size"] = es
        LOGGER.info("Running effect_size=%s -> %s", es, ws)
        model.execute(args)
        cases = total_preventable_cases(ws, label)
        LOGGER.info("  effect_size=%s -> preventable cases = %.1f", es, cases)
        rows.append((label, es, cases))

    # Write the grid: cases (per effect_size) x cost bands (analytic).
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["effect_size_label", "effect_size", "preventable_cases",
                    *COST_RATES.keys()])   # keys already carry the 'cost_' prefix
        for label, es, cases in rows:
            costs = [round(cases * c) for c in COST_RATES.values()]
            w.writerow([label, es, round(cases, 1), *costs])
    LOGGER.info("Wrote %s", SUMMARY_CSV)
    LOGGER.info("Interpretation: rows = greenness effect-size scenarios (RR); columns = "
                "societal cost-per-case bands. Central estimate = es_central_rr x "
                "cost_central_21280.")


if __name__ == "__main__":
    main()
