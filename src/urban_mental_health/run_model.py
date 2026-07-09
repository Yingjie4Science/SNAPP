#!/usr/bin/env python3
"""
Run the InVEST Urban Mental Health model (new in InVEST 3.19) via its Python API.

Verified against the model source at:
    natcap/invest -> src/natcap/invest/urban_mental_health/urban_mental_health.py
The package exposes execute, validate, and MODEL_SPEC:
    from natcap.invest import urban_mental_health
    urban_mental_health.execute(args)

WHAT THE MODEL DOES
    Estimates preventable cases (and optionally societal cost) of a mental-health
    outcome (e.g. depression) attributable to residential greenness. It averages
    greenness (NDVI) within a `search_radius` around each populated pixel, applies
    an exposure-response `effect_size`, and combines that with a baseline
    prevalence rate and a population raster. The model ALWAYS compares a baseline
    against an alternate (greening) scenario -- either two NDVI rasters
    (model_option='ndvi') or two LULC rasters (model_option='lulc').
    Main outputs: preventable_cases (+ preventable_cost if health_cost_rate given)
    plus per-admin-unit summary vector/table.

INSTALL  (docs: https://invest.readthedocs.io/en/latest/installing.html)
    natcap.invest depends on GDAL binaries, so conda-forge is the recommended
    route (and the only easy one on Apple Silicon Macs):
        conda create -n invest -c conda-forge python=3.11 natcap.invest
        conda activate invest
    pip works only if a GDAL toolchain is already present:
        pip install natcap.invest       # fails with a compile error if no GDAL

REQUIRED INPUTS  (put files under data/urban-mental-health/inputs/)
    aoi_path                    polygon vector, PROJECTED IN METERS. Must be
                                smaller than the rasters by >= search_radius
                                (the model buffers the AOI by search_radius).
    population_raster           integer raster, people per pixel, projected (m).
    search_radius               meters (> 0). <=300 m is typical for mental health.
    effect_size                 relative risk per +0.1 NDVI, in (0, 1]
                                (<1 = protective). Take from published epidemiology.
    baseline_prevalence_vector  polygon vector with a `risk_rate` field (a ratio).
    model_option                'ndvi' or 'lulc'.
    ndvi_base + ndvi_alt        required when model_option='ndvi' (float rasters,
                                extending beyond the AOI by >= search_radius).
    lulc_base + lulc_alt + lulc_attr_csv   required when model_option='lulc'.
    (optional) health_cost_rate  societal cost per case (currency) -> valuation.
    (optional) results_suffix, n_workers.

CAVEAT ON NDVI RESOLUTION
    This project's Copernicus NDVI is 300 m. Mental-health studies use a
    <=300 m search RADIUS, so 300 m PIXELS are very coarse here (one pixel ~ the
    whole buffer). For a real SF analysis prefer 10 m Sentinel-2 or 30 m Landsat
    NDVI; the 300 m data is fine for wiring/testing the pipeline.

USAGE
    python src/urban_mental_health/run_model.py --spec      # list inputs + required
    python src/urban_mental_health/run_model.py --validate  # check inputs only
    python src/urban_mental_health/run_model.py             # run the model
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("urban_mental_health_runner")

# --------------------------------------------------------------------------
# Project paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]          # project root (SNAPP)
DATASET_DIR = BASE_DIR / "data" / "urban-mental-health"
INPUTS = DATASET_DIR / "inputs"
WORKSPACE = DATASET_DIR / "workspace"                    # model writes results here

# Baseline NDVI can be derived from the SF NDVI 2024 downloads
# (data/sf-ndvi-2024/processed/*): composite the dekads into one baseline raster.
SF_NDVI_PROCESSED = BASE_DIR / "data" / "sf-ndvi-2024" / "processed"


# --------------------------------------------------------------------------
# Import the model
# --------------------------------------------------------------------------
def load_model():
    try:
        from natcap.invest import urban_mental_health as mod
    except ImportError as e:
        sys.exit(
            "Could not import natcap.invest.urban_mental_health.\n"
            f"  ({e})\n"
            "Install it, e.g.:\n"
            "  conda create -n invest -c conda-forge python=3.11 natcap.invest\n"
            "and run this script inside that environment."
        )
    return mod


# --------------------------------------------------------------------------
# Build the args dictionary  (ids verified against MODEL_SPEC)
# --------------------------------------------------------------------------
def build_args() -> dict:
    args = {
        # --- core ---
        "workspace_dir": str(WORKSPACE),
        "results_suffix": "sf_2024",
        # "n_workers": -1,                # optional: -1 = run in the main process

        # --- spatial inputs ---
        "aoi_path": str(INPUTS / "sf_aoi.gpkg"),                 # projected in METERS
        "population_raster": str(INPUTS / "sf_population.tif"),  # int, people/pixel
        "search_radius": 300.0,                                  # meters (> 0)

        # --- exposure-response ---
        # Relative risk per +0.1 NDVI; must be in (0, 1] (<1 = protective). The
        # model computes PC = (1 - exp(ln(effect_size)*10*dNDVI)) * baseline_cases.
        # Default from a depression meta-analysis: OR = 0.931 (95% CI 0.887-0.977)
        # per +0.1 NDVI. Liu et al. (2023), Environmental Research 231:116303,
        # DOI 10.1016/j.envres.2023.116303 (PMID 37268208). NOTE it's an odds
        # ratio used here as a risk ratio — fine for a first pass; revisit for
        # your exact outcome/region. Sensitivity bounds: 0.887 (low) - 0.977 (high).
        "effect_size": 0.93,

        # --- baseline burden ---
        # Polygon vector of admin units; must have a `risk_rate` field (a ratio).
        "baseline_prevalence_vector": str(INPUTS / "baseline_prevalence.gpkg"),

        # --- scenario option: compare baseline vs. alternate NDVI ---
        "model_option": "ndvi",                                  # 'ndvi' or 'lulc'
        "ndvi_base": str(INPUTS / "sf_ndvi_2024_gee.tif"),       # baseline (GEE route)
        "ndvi_alt": str(INPUTS / "sf_ndvi_scenario.tif"),        # from make_ndvi_scenario.py

        # If instead model_option == 'lulc', supply these and drop the ndvi_* keys:
        # "lulc_base": str(INPUTS / "lulc_base.tif"),
        # "lulc_alt": str(INPUTS / "lulc_alt.tif"),
        # "lulc_attr_csv": str(INPUTS / "lulc_attributes.csv"),  # cols: lucode, exclude, ndvi

        # --- optional: economic valuation ---
        # "health_cost_rate": 5000.0,     # societal cost per case (currency units)
    }
    return args


def print_spec(model):
    """List the model's declared inputs and whether each is required."""
    spec = model.MODEL_SPEC
    print(f"Model: {spec.model_id} - {spec.model_title}\n")
    print(f"{'input id':32} {'required':10} type")
    print("-" * 60)
    for inp in spec.inputs:
        req = getattr(inp, "required", True)
        print(f"{inp.id:32} {str(req):10} {type(inp).__name__}")


def ndvi_prep_note():
    # `ndvi_base` needs ONE raster; build it from the 36 dekad files with the
    # companion helper, then supply an `ndvi_alt` greening scenario yourself.
    LOGGER.info(
        "ndvi_base expects ONE NDVI raster. Build it from the 2024 dekads in %s via:\n"
        "    python src/sf_ndvi/composite_ndvi.py\n"
        "Both NDVI rasters must extend beyond the AOI by at least the search radius.",
        SF_NDVI_PROCESSED,
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Run InVEST Urban Mental Health model.")
    parser.add_argument("--spec", action="store_true",
                        help="Print the model's inputs (from MODEL_SPEC) and exit.")
    parser.add_argument("--validate", action="store_true",
                        help="Validate inputs with the model's validate() and exit.")
    cli = parser.parse_args()

    model = load_model()

    if cli.spec:
        print_spec(model)
        return

    args = build_args()
    ndvi_prep_note()

    # The model's own validator returns a list of (keys, message) warnings.
    warnings = model.validate(args)
    if warnings:
        LOGGER.warning("validate() reported issues:")
        for keys, message in warnings:
            LOGGER.warning("  %s: %s", keys, message)
        if cli.validate:
            sys.exit(1)
        LOGGER.warning("Fix the above before trusting results (continuing anyway).")
    else:
        LOGGER.info("validate(): all inputs OK.")

    if cli.validate:
        return

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Running Urban Mental Health model -> %s", WORKSPACE)
    model.execute(args)
    LOGGER.info("Done. Outputs (preventable_cases, summary vector/table, ...) in %s",
                WORKSPACE)


if __name__ == "__main__":
    main()
