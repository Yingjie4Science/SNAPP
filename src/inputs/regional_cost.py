#!/usr/bin/env python3
"""
Regionalize the pooled national SOCIETAL cost per depression case using MEPS.

Why / justification
    Our headline cost is a national pooled societal cost per prevalent case
    (~$21,280, 2024 USD; see docs/societal_cost_of_depression.md), built from
    Greenberg cost-of-illness components:
        workplace_productivity 0.61, direct_comorbid 0.24,
        direct_mdd_treatment 0.112, suicide_related 0.04
    Two of these vary geographically for known reasons:
      - the DIRECT MEDICAL share (direct_mdd_treatment + direct_comorbid ~ 0.35)
        tracks regional healthcare PRICES, which MEPS measures directly as mean
        expenditure per treated case by Census region;
      - the WAGE-DRIVEN share (workplace_productivity + suicide_related ~ 0.65)
        tracks regional WAGES, for which an optional wage index can be supplied.

    So we scale the national cost by a region multiplier that is a
    share-weighted blend of a medical-price ratio (from MEPS) and a wage ratio:

        multiplier_r = s_med * (MEPS_r / MEPS_national)
                     + s_wage * (wage_r / wage_national)

    where s_med, s_wage are the component shares above. With no wage index the
    wage term is held at 1.0 (only the medical third is regionalized) — a
    conservative partial regionalization using ONLY data we already have (MEPS).

    Honesty note: because only ~35% of the societal cost is regionalized via
    MEPS, and MEPS regional spread is modest, the resulting regional cost spread
    is small (typically a few percent). This is a refinement, not a driver — the
    dominant cost uncertainty remains the anchor and the societal-vs-direct basis.
    Multipliers are re-centered to a population-weighted mean of 1.0 so the
    national total is preserved.

Writes  config/cost_by_region.csv:  region, meps_ratio, wage_ratio, multiplier, cost_rate_usd
run_city.py can consume it via --cost-by-region (maps county state -> region).

REQUIREMENTS  (conda env `snapp`): openpyxl (via estimate_health_cost)
USAGE
    python src/inputs/regional_cost.py                     # MEPS-only (partial)
    python src/inputs/regional_cost.py --wage-index config/wage_index.csv
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("regional_cost")

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_CSV = BASE_DIR / "config" / "cost_by_region.csv"
REGIONS = ["Northeast", "Midwest", "South", "West"]
# Census-region population weights (2020, share of US) for re-centering + national mean.
REGION_POP_WEIGHT = {"Northeast": 0.171, "Midwest": 0.208, "South": 0.384, "West": 0.237}


def load_wage_index(path: Path) -> dict:
    """Optional region -> wage level (any consistent unit). Ratios are computed here."""
    idx = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            reg = (r.get("region") or "").strip()
            if reg in REGIONS:
                idx[reg] = float(r["wage"])
    return idx


def main():
    ap = argparse.ArgumentParser(description="Regionalize societal cost via MEPS (+ optional wages).")
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--anchor", default="pooled")
    ap.add_argument("--wage-index", type=Path, default=None,
                    help="Optional CSV (region,wage) to regionalize the wage-driven share too.")
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    cli = ap.parse_args()

    import estimate_health_cost as ehc

    # National pooled societal cost (the number we already report).
    comps = ehc.societal_components(cli.anchor, cli.year, wage_factor=1.0)
    national_cost = sum(comps.values())
    s_med = ehc.COMPONENT_SHARES["direct_mdd_treatment"] + ehc.COMPONENT_SHARES["direct_comorbid"]
    s_wage = ehc.COMPONENT_SHARES["workplace_productivity"] + ehc.COMPONENT_SHARES["suicide_related"]

    # MEPS direct medical cost per treated case, by region + national ("All persons").
    if not ehc.DEFAULT_MEPS.exists():
        sys.exit(f"MEPS file not found: {ehc.DEFAULT_MEPS}. Needed for regional ratios.")
    meps = {r: ehc.meps_direct(ehc.DEFAULT_MEPS, r) for r in REGIONS}
    meps_nat = ehc.meps_direct(ehc.DEFAULT_MEPS, "All persons")

    wages = load_wage_index(cli.wage_index) if cli.wage_index else {}
    wage_nat = (sum(REGION_POP_WEIGHT[r] * wages[r] for r in REGIONS)
                if len(wages) == len(REGIONS) else None)

    raw = {}
    for r in REGIONS:
        meps_ratio = meps[r] / meps_nat
        wage_ratio = (wages[r] / wage_nat) if wage_nat else 1.0
        raw[r] = s_med * meps_ratio + s_wage * wage_ratio

    # Re-center so the population-weighted mean multiplier is exactly 1.0
    # (preserves the national total; regions only redistribute).
    wmean = sum(REGION_POP_WEIGHT[r] * raw[r] for r in REGIONS)
    mult = {r: raw[r] / wmean for r in REGIONS}

    cli.out.parent.mkdir(parents=True, exist_ok=True)
    with open(cli.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "meps_ratio", "wage_ratio", "multiplier", "cost_rate_usd"])
        for r in REGIONS:
            meps_ratio = meps[r] / meps_nat
            wage_ratio = (wages[r] / wage_nat) if wage_nat else 1.0
            w.writerow([r, round(meps_ratio, 4), round(wage_ratio, 4),
                        round(mult[r], 4), round(national_cost * mult[r])])
    LOGGER.info("National pooled societal cost: $%.0f (%d USD)", national_cost, cli.year)
    LOGGER.info("Regionalized (%s share medical, %s wage; wage index: %s):",
                round(s_med, 3), round(s_wage, 3), "yes" if wages else "no (held at 1.0)")
    for r in REGIONS:
        LOGGER.info("  %-9s multiplier %.3f -> $%.0f", r, mult[r], national_cost * mult[r])
    LOGGER.info("Wrote %s. run_city.py --cost-by-region can consume it.", cli.out)


if __name__ == "__main__":
    main()
