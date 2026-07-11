#!/usr/bin/env python3
"""
Estimate the model's `health_cost_rate` (cost per depression case) on two bases:

  --basis societal  (default)  Full annual SOCIETAL cost per prevalent case,
        derived from Greenberg et al. 2021 (PharmacoEconomics 39:653-665): total
        incremental US MDD burden $326.2B (2018, 2020 USD) / ~17.5M adults with
        MDD, split into components and inflation-adjusted to --year. ~$22k (2024).
        See docs/societal_cost_of_depression.md.

  --basis direct               Direct medical cost per TREATED case from MEPS
        ("mean expenditure per person with care", by census region). ~$1.4-1.8k.

Writes:
  - inputs/health_cost_rate.txt        the single value run_model.py reads
  - inputs/health_cost_components.csv  per-case component breakdown (societal)

REQUIREMENTS
    conda env: openpyxl   (for the MEPS direct figure / cross-check)

USAGE
    python src/inputs/estimate_health_cost.py                      # societal, 2024, West
    python src/inputs/estimate_health_cost.py --basis direct       # MEPS direct medical
    python src/inputs/estimate_health_cost.py --year 2024 --wage-factor 1.15  # SF-adjusted
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("Missing dep. Install: conda install -c conda-forge openpyxl")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("estimate_health_cost")

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_MEPS = BASE_DIR / "data" / "urban-mental-health" / "raw" / "meps"
DEFAULT_MEPS = RAW_MEPS / "MEPS_HC_MedicalConditions_CrossSectional.xlsx"
INPUTS = BASE_DIR / "data" / "urban-mental-health" / "inputs"
OUT_RATE = INPUTS / "health_cost_rate.txt"
OUT_COMPONENTS = INPUTS / "health_cost_components.csv"
REGIONS = ["All persons", "Northeast", "Midwest", "South", "West"]

# --- Greenberg et al. 2021 societal-burden constants (2020 USD) ---
GREENBERG_TOTAL_2018 = 326.2e9      # incremental US adult MDD burden, 2018
MDD_ADULTS_2018 = 17.5e6            # US adults with MDD, 2018 (NIMH ~17.7M)
# Component shares of the 2018 burden (workplace-heavy). Sum ~1.00.
COMPONENT_SHARES = {
    "workplace_productivity": 0.61,   # absenteeism + presenteeism
    "direct_comorbid": 0.24,          # excess care for co-occurring conditions
    "direct_mdd_treatment": 0.112,    # ~ what MEPS measures
    "suicide_related": 0.04,
}
# CPI-U annual averages (BLS) for inflation adjustment from the 2020 base.
CPI_U = {2020: 258.811, 2021: 270.970, 2022: 292.655, 2023: 304.702, 2024: 313.689}


def meps_direct(xlsx: Path, region: str, condition: str = "Depression") -> float:
    """MEPS mean expenditure per person WITH CARE for a condition x region."""
    ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)["Table Data"]
    for row in ws.iter_rows(values_only=True):
        cond, group, measure, value = row[0], row[2], row[3], row[4]
        if (cond and str(cond).strip().lower() == condition.lower()
                and str(group).strip() == region
                and str(measure).strip() == "Estimate"):
            return float(value)
    sys.exit(f"No '{condition}' / '{region}' / Estimate row in {xlsx.name}.")


def societal_components(year: int, wage_factor: float) -> dict:
    """Per-prevalent-case societal cost by component, inflated to `year`."""
    if year not in CPI_U:
        sys.exit(f"--year must be one of {sorted(CPI_U)} (extend CPI_U to add more).")
    per_case_2020 = GREENBERG_TOTAL_2018 / MDD_ADULTS_2018   # ~$18,640
    cpi = CPI_U[year] / CPI_U[2020]
    comps = {}
    for name, share in COMPONENT_SHARES.items():
        val = per_case_2020 * share * cpi
        # Wage-driven components scale with a local wage factor (default 1.0).
        if name in ("workplace_productivity", "suicide_related"):
            val *= wage_factor
        comps[name] = val
    return comps


def main():
    ap = argparse.ArgumentParser(description="Estimate health_cost_rate (societal or direct).")
    ap.add_argument("--basis", choices=["societal", "direct"], default="societal")
    ap.add_argument("--year", type=int, default=2024, help="Target USD year (societal).")
    ap.add_argument("--region", default="West", choices=REGIONS,
                    help="Census region for the MEPS direct figure.")
    ap.add_argument("--wage-factor", type=float, default=1.0,
                    help="Scale wage-driven components (e.g. 1.15 for SF). Default 1.0.")
    ap.add_argument("--meps", type=Path, default=DEFAULT_MEPS)
    cli = ap.parse_args()

    INPUTS.mkdir(parents=True, exist_ok=True)

    # MEPS direct figure (used as the value for --basis direct, and as a cross-check).
    meps_val = meps_direct(cli.meps, cli.region) if cli.meps.exists() else None

    if cli.basis == "direct":
        if meps_val is None:
            sys.exit(f"MEPS file not found: {cli.meps}")
        rate = meps_val
        LOGGER.info("DIRECT medical cost per treated case (%s, MEPS 2023): $%.0f",
                    cli.region, rate)
    else:
        comps = societal_components(cli.year, cli.wage_factor)
        rate = sum(comps.values())
        # Write the component breakdown.
        with open(OUT_COMPONENTS, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["component", "share", f"per_case_usd_{cli.year}"])
            for name, share in COMPONENT_SHARES.items():
                w.writerow([name, share, round(comps[name])])
            w.writerow(["TOTAL", round(sum(COMPONENT_SHARES.values()), 3), round(rate)])
        LOGGER.info("SOCIETAL cost per prevalent case (%d USD, wage_factor=%.2f): $%.0f",
                    cli.year, cli.wage_factor, rate)
        for name, val in comps.items():
            LOGGER.info("    %-24s $%8.0f  (%.1f%%)", name, val, 100 * COMPONENT_SHARES[name])
        LOGGER.info("Wrote component breakdown -> %s", OUT_COMPONENTS)
        if meps_val is not None:
            LOGGER.info("Cross-check: MEPS direct (%s) = $%.0f vs societal direct-MDD "
                        "component $%.0f", cli.region, meps_val,
                        comps["direct_mdd_treatment"])

    OUT_RATE.write_text(f"{rate:.0f}\n")
    LOGGER.info("Wrote %s = %.0f -> run_model.py uses this as health_cost_rate.",
                OUT_RATE, rate)
    if cli.basis == "societal":
        LOGGER.info("Basis: full societal (Greenberg 2021). See "
                    "docs/societal_cost_of_depression.md for method + caveats.")


if __name__ == "__main__":
    main()
