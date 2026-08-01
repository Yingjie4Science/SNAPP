#!/usr/bin/env python3
"""
Sensitivity analysis for the Urban Mental Health model (SF).

Varies the three key assumptions and reports how the results move:
  - Liu odds ratio: 0.887 / 0.931 / 0.977 per +0.1 NDVI
  - p0 reference risk: locked national low-NDVI-quartile estimate plus Hystad
    et al. outcome-definition scenarios 0.064 / 0.096 / 0.115
  - health_cost_rate : $17,000 (low) / $21,280 (pooled central) / $23,000 (high)

Each OR × p0 pair is converted to the RR InVEST expects and run spatially.
Preventable COST scales linearly with the cost rate, so cost bands are computed
analytically. The three Hystad values are distinct, overlapping outcome
definitions from one Canadian cohort; they are sensitivity anchors only.

REQUIREMENTS  (conda env `snapp`): natcap.invest, rasterio, numpy
USAGE
    python src/urban_mental_health/run_sensitivity.py
Outputs:
    data/urban-mental-health/runs/sf/sensitivity/<label>/   (per-run workspaces)
    results/summaries/sensitivity_summary.csv
"""

import csv
import logging
import sys
from pathlib import Path

# Import the SF model config (build_args, load_model, paths) from the sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("run_sensitivity")

_M = run_model._MODEL
ODDS_RATIOS = {
    "or_low_more_protective": float(_M.get("effect_size_or_low", 0.887)),
    "or_central_published": float(_M.get("effect_size_or", 0.931)),
    "or_high_less_protective": float(_M.get("effect_size_or_high", 0.977)),
}
P0_SCENARIOS = {
    "national_low_ndvi_quartile_p0": float(_M.get("baseline_risk_p0", 0.191066)),
    "hystad_phq9_ge10": 0.064,
    "hystad_self_reported_diagnosis": 0.096,
    "hystad_health_record_diagnosis": 0.115,
}
COST_RATES = {"cost_low_17000": 17000.0, "cost_central_21280": 21280.0, "cost_high_23000": 23000.0}

WS_ROOT = run_model.RUNS / "sensitivity"                    # runs (gitignored)
SUMMARY_CSV = run_model.RESULTS_SUMMARIES / "sensitivity_summary.csv"  # committed


def or_to_rr(odds_ratio: float, p0: float) -> float:
    return odds_ratio / (1.0 - p0 + p0 * odds_ratio)


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
    for p0_label, p0 in P0_SCENARIOS.items():
        for or_label, odds_ratio in ODDS_RATIOS.items():
            effect_size = or_to_rr(odds_ratio, p0)
            # The configured run stores rounded RRs. Use those exact values for
            # its three rows so the central sensitivity row reproduces the
            # headline model run rather than differing only by rounding.
            if p0_label == "national_low_ndvi_quartile_p0":
                configured_rr = {
                    "or_low_more_protective": _M.get("effect_size_low"),
                    "or_central_published": _M.get("effect_size"),
                    "or_high_less_protective": _M.get("effect_size_high"),
                }.get(or_label)
                if configured_rr is not None:
                    effect_size = float(configured_rr)
            label = f"{p0_label}__{or_label}"
            ws = WS_ROOT / label
            ws.mkdir(parents=True, exist_ok=True)
            args = dict(base)
            args["workspace_dir"] = str(ws)
            args["results_suffix"] = label
            args["effect_size"] = effect_size
            LOGGER.info("Running p0=%s OR=%s RR=%s -> %s",
                        p0, odds_ratio, effect_size, ws)
            model.MODEL_SPEC.execute(args, create_logfile=True)
            cases = total_preventable_cases(ws, label)
            LOGGER.info("  p0=%s OR=%s RR=%s -> cases=%.1f",
                        p0, odds_ratio, effect_size, cases)
            rows.append({
                "effect_size_label": label,
                "p0_label": p0_label,
                "p0": p0,
                "or_label": or_label,
                "odds_ratio": odds_ratio,
                "effect_size": effect_size,
                "preventable_cases": cases,
            })

    # Write the grid: cases (per effect_size) x cost bands (analytic).
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_CSV, "w", newline="") as fh:
        fields = ["effect_size_label", "p0_label", "p0", "or_label",
                  "odds_ratio", "effect_size", "preventable_cases",
                  *COST_RATES.keys()]
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cases = row["preventable_cases"]
            writer.writerow({
                **row,
                "p0": f"{row['p0']:.3f}",
                "odds_ratio": f"{row['odds_ratio']:.3f}",
                "effect_size": f"{row['effect_size']:.6f}",
                "preventable_cases": round(cases, 1),
                **{label: round(cases * rate) for label, rate in COST_RATES.items()},
            })
    LOGGER.info("Wrote %s", SUMMARY_CSV)
    LOGGER.info("Interpretation: rows = OR x p0 scenarios converted to RR; "
                "columns = societal cost-per-case bands. The national "
                "low-NDVI-quartile p0 is the primary U.S. specification.")


if __name__ == "__main__":
    main()
