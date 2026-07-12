#!/usr/bin/env python3
"""
Run the model across MULTIPLE greening scenarios in one go and compare them.

Each scenario is just a different `ndvi_alt` raster (produced by the scenario
generators in src/inputs/). This runs the model once per scenario into its own
workspace and writes a comparison CSV of preventable cases and cost.

Scenarios come from config.yaml `scenarios:` (label -> ndvi_alt filename in
inputs/); any listed file that doesn't exist yet is skipped with a note, so you
can generate a subset and compare just those.

REQUIREMENTS  (conda env `snapp`): natcap.invest, rasterio, numpy, pyyaml
USAGE
    # first generate the scenarios you want, e.g.:
    #   python src/inputs/ndvi/make_ndvi_scenario.py --mode greenable
    #   python src/inputs/ndvi/scenario_lulc_masked.py --lulc .../nlcd_landcover.tif
    #   python src/inputs/ndvi/scenario_canopy_target.py --target-ndvi 0.60
    python src/urban_mental_health/run_scenarios.py
Outputs:
    data/urban-mental-health/runs/sf_scenarios/<label>/
    data/urban-mental-health/runs/sf_scenarios/scenario_comparison.csv
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model                      # noqa: E402  (build_args, load_model, INPUTS, CFG)
from run_sensitivity import total_preventable_cases  # noqa: E402  (raster sum helper)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("run_scenarios")

WS_ROOT = run_model.RUNS / "sf_scenarios"                    # runs (gitignored)
COMPARISON_CSV = run_model.RESULTS_SUMMARIES / "scenario_comparison.csv"  # committed
COST_FILE = run_model.INPUTS / "health_cost_rate.txt"

# Default scenario set if config.yaml has no `scenarios:` block.
DEFAULT_SCENARIOS = {
    "greenable": "ndvi_scenario.tif",
    "lulc_masked": "ndvi_scenario_lulc.tif",
    "canopy_target": "ndvi_scenario_canopy.tif",
}


def scenario_set() -> dict:
    return run_model.CFG.get("scenarios") or DEFAULT_SCENARIOS


def main():
    WS_ROOT.mkdir(parents=True, exist_ok=True)
    model = run_model.load_model()
    base = run_model.build_args()
    cost = float(COST_FILE.read_text().strip()) if COST_FILE.exists() else None

    scenarios = scenario_set()
    rows = []
    for label, fname in scenarios.items():
        alt = run_model.INPUTS / fname
        if not alt.exists():
            LOGGER.warning("skip '%s' — %s not found (generate it first).", label, alt.name)
            continue
        ws = WS_ROOT / label
        ws.mkdir(parents=True, exist_ok=True)
        args = dict(base)
        args["ndvi_alt"] = str(alt)
        args["workspace_dir"] = str(ws)
        args["results_suffix"] = label
        LOGGER.info("Running scenario '%s' (ndvi_alt=%s)...", label, fname)
        model.execute(args)
        cases = total_preventable_cases(ws, label)
        total_cost = cases * cost if cost else None
        LOGGER.info("  '%s': %.0f preventable cases%s", label, cases,
                    f", ${total_cost:,.0f}" if total_cost else "")
        rows.append((label, fname, cases, total_cost))

    if not rows:
        sys.exit("No scenarios ran — generate at least one ndvi_alt raster first.")

    COMPARISON_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPARISON_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario", "ndvi_alt", "preventable_cases",
                    f"preventable_cost_usd (@ ${cost:,.0f}/case)" if cost else "preventable_cost_usd"])
        for label, fname, cases, total_cost in rows:
            w.writerow([label, fname, round(cases, 1),
                        round(total_cost) if total_cost is not None else ""])
    LOGGER.info("Wrote %s", COMPARISON_CSV)
    LOGGER.info("Compare scenarios there; cost uses the central health_cost_rate. "
                "For a full grid, also run run_sensitivity.py per scenario.")


if __name__ == "__main__":
    main()
