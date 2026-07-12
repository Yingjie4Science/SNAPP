#!/usr/bin/env python3
"""
Build a per-county ADULT (18+) population fraction lookup from Census ACS.

CDC PLACES depression is an ADULT (18+) prevalence, so the population fed to the
model should be the 18+ count. County age structure varies a lot (college towns
vs. retirement counties), so a per-county 18+ share is more accurate than the
flat 0.86 national default. This script pulls the 18+ and total population per
county from the ACS 5-year API and writes:

    config/adult_fraction.csv   ->   GEOID, name, adult_fraction

run_city.py reads that file automatically (if present) and uses the county's
own fraction, falling back to --adult-fraction (0.86) for any county not listed.

Variables (ACS 5-year detail tables, no API key needed for light use):
    B09021_001E  population 18 years and over  (universe = adults 18+)
    B01003_001E  total population
    adult_fraction = B09021_001E / B01003_001E

REQUIREMENTS: requests
USAGE
    python src/inputs/fetch_adult_fraction.py                 # 2023 ACS5, all counties
    python src/inputs/fetch_adult_fraction.py --year 2022
    python src/inputs/fetch_adult_fraction.py --api-key YOURKEY   # optional, higher limits
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dep 'requests'. Install the `snapp` env or: pip install requests")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fetch_adult_fraction")

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_CSV = BASE_DIR / "config" / "adult_fraction.csv"
ADULT_VAR = "B09021_001E"     # population 18 years and over
TOTAL_VAR = "B01003_001E"     # total population


def main():
    ap = argparse.ArgumentParser(description="Per-county ACS 18+ fraction lookup.")
    ap.add_argument("--year", type=int, default=2023, help="ACS 5-year vintage (default 2023).")
    ap.add_argument("--api-key", default=None, help="Optional Census API key (higher rate limit).")
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    cli = ap.parse_args()

    url = f"https://api.census.gov/data/{cli.year}/acs/acs5"
    params = {"get": f"NAME,{ADULT_VAR},{TOTAL_VAR}", "for": "county:*"}
    if cli.api_key:
        params["key"] = cli.api_key
    LOGGER.info("Querying ACS %d 5-year: %s", cli.year, url)
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    header, rows = data[0], data[1:]
    idx = {name: i for i, name in enumerate(header)}

    out_rows, skipped = [], 0
    for row in rows:
        state = row[idx["state"]]
        county = row[idx["county"]]
        geoid = f"{state.zfill(2)}{county.zfill(3)}"
        name = row[idx["NAME"]]
        try:
            adults = float(row[idx[ADULT_VAR]])
            total = float(row[idx[TOTAL_VAR]])
        except (TypeError, ValueError):
            skipped += 1
            continue
        if total <= 0:
            skipped += 1
            continue
        frac = adults / total
        if not (0.4 <= frac <= 1.0):        # sanity guard against junk rows
            LOGGER.warning("%s (%s): implausible adult_fraction %.3f — skipping.",
                           geoid, name, frac)
            skipped += 1
            continue
        out_rows.append({"GEOID": geoid, "name": name, "adult_fraction": round(frac, 4)})

    out_rows.sort(key=lambda d: d["GEOID"])
    cli.out.parent.mkdir(parents=True, exist_ok=True)
    with open(cli.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["GEOID", "name", "adult_fraction"])
        w.writeheader()
        w.writerows(out_rows)

    fr = [d["adult_fraction"] for d in out_rows]
    LOGGER.info("Wrote %s: %d counties (skipped %d).", cli.out, len(out_rows), skipped)
    if fr:
        LOGGER.info("adult_fraction range %.3f-%.3f, mean %.3f",
                    min(fr), max(fr), sum(fr) / len(fr))


if __name__ == "__main__":
    main()
