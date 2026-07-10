#!/usr/bin/env python3
"""
Extract the depression cost-per-case for the model's `health_cost_rate` from MEPS.

SOURCE
    data/urban-mental-health/raw/meps/MEPS_HC_MedicalConditions_CrossSectional.xlsx
    Metric: "Mean expenditure per person with care ($) by condition, US, 2023",
    broken out by census region. San Francisco is in the WEST region.

WHAT IT IS (caveat)
    This is a DIRECT MEDICAL cost per treated case — it does NOT include indirect
    societal costs (lost productivity, informal care, etc.), so it's a
    conservative lower bound on the "societal cost per case" the model asks for.

OUTPUT
    Writes the dollar value to data/urban-mental-health/inputs/health_cost_rate.txt,
    which run_model.py reads automatically.

REQUIREMENTS
    conda env: openpyxl   (already in environment.yml)

USAGE
    python src/inputs/extract_meps_cost.py                 # Depression, West region
    python src/inputs/extract_meps_cost.py --region "All persons"   # national
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("Missing dep. Install: conda install -c conda-forge openpyxl")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("extract_meps_cost")

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_MEPS = BASE_DIR / "data" / "urban-mental-health" / "raw" / "meps"
DEFAULT_MEPS = RAW_MEPS / "MEPS_HC_MedicalConditions_CrossSectional.xlsx"
DEFAULT_OUT = BASE_DIR / "data" / "urban-mental-health" / "inputs" / "health_cost_rate.txt"
REGIONS = ["All persons", "Northeast", "Midwest", "South", "West"]


def extract_estimate(xlsx: Path, condition: str, region: str) -> float:
    """Return the MEPS mean-expenditure Estimate for a condition x region."""
    ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)["Table Data"]
    for row in ws.iter_rows(values_only=True):
        cond, _body, group, measure, value = row[0], row[1], row[2], row[3], row[4]
        if (cond and str(cond).strip().lower() == condition.lower()
                and str(group).strip() == region
                and str(measure).strip() == "Estimate"):
            return float(value)
    sys.exit(f"No '{condition}' / '{region}' / Estimate row found in {xlsx.name}.")


def main():
    ap = argparse.ArgumentParser(description="Extract MEPS depression cost-per-case.")
    ap.add_argument("--meps", type=Path, default=DEFAULT_MEPS, help="MEPS .xlsx file.")
    ap.add_argument("--condition", default="Depression", help="Condition Category.")
    ap.add_argument("--region", default="West", choices=REGIONS, help="Census region.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output .txt.")
    cli = ap.parse_args()

    if not cli.meps.exists():
        sys.exit(f"MEPS file not found: {cli.meps}")

    value = extract_estimate(cli.meps, cli.condition, cli.region)
    cli.output.parent.mkdir(parents=True, exist_ok=True)
    cli.output.write_text(f"{value:.0f}\n")
    LOGGER.info("%s cost per treated case (%s, MEPS 2023): $%.0f",
                cli.condition, cli.region, value)
    LOGGER.info("Wrote %s -> run_model.py will use it as health_cost_rate.", cli.output)
    LOGGER.info("Note: direct medical cost only (excludes indirect/societal costs).")


if __name__ == "__main__":
    main()
