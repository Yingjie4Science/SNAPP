#!/usr/bin/env python3
"""
Equity analysis: is the greening mental-health benefit pro-poor or pro-rich?

Adapts the inequality framing of Wu et al. (2026, Nature Health) to the US
tract scale. For each neighborhood we take the model's preventable depression
RATE (cases per adult) and rank neighborhoods by a socioeconomic measure
(default: ACS median household income). We then compute a population-weighted
health CONCENTRATION INDEX (CI) and draw the concentration curve.

Interpretation of the concentration index (of the preventable RATE vs income):
  CI < 0  -> benefit concentrates in LOWER-income neighborhoods (pro-poor / equity-
             promoting: greening helps the disadvantaged most)
  CI > 0  -> benefit concentrates in HIGHER-income neighborhoods (pro-rich)
  CI ~ 0  -> benefit spread evenly across the income gradient
CI = 2 * Cov_w(y, R) / mean_w(y), with population weights, y = preventable rate,
R = population-weighted fractional income rank (ascending). (Kakwani et al. 1997.)

Socioeconomic data: ACS 5-year median household income (B19013_001E) and total
population (B01003_001E) per tract, fetched live; or pass --ses-file
(CSV: GEOID,income,population). Preventable cases come from the model summary gpkg.

REQUIREMENTS (conda env `snapp`): geopandas, pandas, numpy, requests, matplotlib
USAGE
    python src/urban_mental_health/equity_analysis.py                 # SF tracts, ACS income
    python src/urban_mental_health/equity_analysis.py --state 06 --county 075 --acs-year 2023
    python src/urban_mental_health/equity_analysis.py --ses-file config/ses.csv
"""

import argparse
import csv
import glob
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("equity_analysis")

BASE_DIR = Path(__file__).resolve().parents[2]
WORKSPACE = BASE_DIR / "data" / "urban-mental-health" / "runs" / "sf_baseline"
RESULTS = BASE_DIR / "results"
OUT_MD = RESULTS / "summaries" / "equity_summary.md"
FIG = RESULTS / "figures" / "equity_concentration_curve.png"
INCOME_VAR, POP_VAR = "B19013_001E", "B01003_001E"


def load_local_env() -> None:
    """Load private, machine-local settings without using the shared-drive .env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.home() / ".config" / "snapp" / ".env")


def fetch_acs(state: str, county: str, year: int, api_key: str | None = None) -> dict:
    """GEOID -> (median_income, population) per tract from ACS 5-year."""
    import requests
    # Build the URL by hand: the space in `in=state:.. county:..` MUST be %20;
    # requests' dict-encoding turns it into '+', which the Census API rejects
    # (returning a plain-text error that then breaks .json()).
    url = (f"https://api.census.gov/data/{year}/acs/acs5?"
           f"get=NAME,{INCOME_VAR},{POP_VAR}&for=tract:*"
           f"&in=state:{state}%20county:{county}")
    params = {"key": api_key} if api_key else None
    r = requests.get(url, params=params, timeout=120)
    if r.status_code != 200 or not r.text.lstrip().startswith("["):
        key_hint = ("Set CENSUS_API_KEY or pass --api-key."
                    if "Missing Key" in r.text else
                    "Check the ACS year/geography or pass --ses-file.")
        sys.exit(f"Census ACS request failed (HTTP {r.status_code}) for year {year}.\n"
                 f"URL: {url}\nResponse (first 300 chars): {r.text[:300]}\n"
                 f"{key_hint}")
    rows = r.json()
    idx = {n: i for i, n in enumerate(rows[0])}
    out = {}
    for row in rows[1:]:
        geoid = row[idx["state"]] + row[idx["county"]] + row[idx["tract"]]
        try:
            inc = float(row[idx[INCOME_VAR]]); pop = float(row[idx[POP_VAR]])
        except (TypeError, ValueError):
            continue
        if inc > 0 and pop > 0:               # ACS uses negatives for missing
            out[geoid] = (inc, pop)
    return out


def load_ses_file(path: Path) -> dict:
    out = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                out[str(r["GEOID"]).strip()] = (float(r["income"]), float(r["population"]))
            except (KeyError, ValueError):
                continue
    return out


def concentration_index(y, w, rankvar):
    """Population-weighted concentration index of y vs ascending rank of rankvar.

    Returns (CI, curve_x, curve_y) where the curve is cumulative population share
    (by ascending rankvar) vs cumulative share of the y*w mass (cases).
    """
    import numpy as np
    y = np.asarray(y, float); w = np.asarray(w, float); rankvar = np.asarray(rankvar, float)
    order = np.argsort(rankvar)                       # poorest -> richest
    y, w = y[order], w[order]
    W = w.sum()
    wshare = w / W
    cum = np.cumsum(wshare)
    R = cum - wshare / 2.0                              # weighted fractional rank (midpoint)
    mu = np.sum(wshare * y)                             # weighted mean of y
    if mu == 0:
        return float("nan"), None, None
    cov = np.sum(wshare * (y - mu) * (R - 0.5))
    ci = 2.0 * cov / mu
    # concentration curve: cumulative pop share vs cumulative case (y*w) share
    mass = y * w
    curve_x = np.concatenate([[0], cum])
    curve_y = np.concatenate([[0], np.cumsum(mass) / mass.sum()])
    return ci, curve_x, curve_y


def main():
    load_local_env()
    ap = argparse.ArgumentParser(description="Equity / concentration-index analysis.")
    ap.add_argument("--summary-gpkg", type=Path,
                    help="Model summary gpkg with GEOID + sum_cases (default: SF run).")
    ap.add_argument("--state", default="06"); ap.add_argument("--county", default="075")
    ap.add_argument("--acs-year", type=int, default=2023)
    ap.add_argument("--api-key", default=os.environ.get("CENSUS_API_KEY"),
                    help="Census API key (default: CENSUS_API_KEY environment variable).")
    ap.add_argument("--ses-file", type=Path, help="CSV GEOID,income,population (skip ACS).")
    cli = ap.parse_args()

    try:
        import geopandas as gpd
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        sys.exit("Missing deps: geopandas, numpy, matplotlib.")

    gpkg = cli.summary_gpkg
    if gpkg is None:
        cands = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.gpkg")))
        if not cands:
            sys.exit("No model summary gpkg found; run the model first.")
        gpkg = Path(cands[0])
    gdf = gpd.read_file(gpkg)
    if "GEOID" not in gdf.columns or "sum_cases" not in gdf.columns:
        sys.exit(f"{gpkg} needs GEOID + sum_cases columns (have {list(gdf.columns)}).")
    gdf["GEOID"] = gdf["GEOID"].astype(str)

    ses = (load_ses_file(cli.ses_file) if cli.ses_file else
           fetch_acs(cli.state, cli.county, cli.acs_year, cli.api_key))
    LOGGER.info("SES records: %d", len(ses))

    rows = []
    for _, r in gdf.iterrows():
        g = r["GEOID"]
        if g in ses and r["sum_cases"] is not None:
            inc, pop = ses[g]
            if pop > 0:
                rows.append((g, float(r["sum_cases"]), inc, pop, float(r["sum_cases"]) / pop))
    if len(rows) < 5:
        sys.exit(f"Only {len(rows)} tracts matched SES — cannot compute a stable index.")

    cases = np.array([x[1] for x in rows])
    inc = np.array([x[2] for x in rows])
    pop = np.array([x[3] for x in rows])
    rate = np.array([x[4] for x in rows])                # preventable cases per adult

    ci, cx, cy = concentration_index(rate, pop, inc)

    # Income deciles (population-weighted-ish, simple decile by tract income).
    order = np.argsort(inc)
    dec_idx = np.array_split(order, 10)
    dec_rows = []
    for d, ix in enumerate(dec_idx, 1):
        dec_rows.append((d, inc[ix].mean(), 1000 * rate[ix].mean(),
                         100 * cases[ix].sum() / cases.sum()))

    # --- concentration curve figure ---
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="0.6", label="line of equality")
    ax.plot(cx, cy, color="#2c7fb8", lw=2, label="concentration curve")
    ax.set_xlabel("Cumulative share of population (poorest → richest)")
    ax.set_ylabel("Cumulative share of preventable cases")
    ax.set_title(f"Equity of greening benefit (CI = {ci:+.3f})")
    ax.legend(fontsize=8); ax.set_aspect("equal")
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=200, bbox_inches="tight"); plt.close(fig)

    lean = ("lower-income neighborhoods (pro-poor / equity-promoting)" if ci < -0.02
            else "higher-income neighborhoods (pro-rich)" if ci > 0.02
            else "evenly across the income gradient")
    lines = ["# Equity analysis — who benefits from greening", "",
             f"_{len(rows)} neighborhoods matched to ACS {cli.acs_year} income._", "",
             "## Concentration index", "",
             f"- **CI = {ci:+.3f}** for the preventable depression *rate* vs. neighborhood "
             f"median income.",
             f"- The benefit concentrates in **{lean}**.",
             "- CI ranges −1…+1; 0 = perfectly even. Negative = the greening benefit is "
             "larger where incomes are lower (an equity win).", "",
             f"![Concentration curve](../figures/{FIG.name})",
             f"<sub>Concentration curve (CI = {ci:+.3f}). Above the diagonal = benefit "
             "concentrated among lower-income residents.</sub>", "",
             "## By income decile (1 = poorest)", "",
             "| decile | mean tract income | preventable cases / 1,000 adults | % of total cases |",
             "|---:|---:|---:|---:|"]
    for d, mi, r1000, share in dec_rows:
        lines.append(f"| {d} | ${mi:,.0f} | {r1000:.1f} | {share:.1f}% |")
    lines += ["", "_Method: population-weighted health concentration index (Kakwani et al., "
              "1997); framing after Wu et al. (2026). Income is a proxy for deprivation; "
              "swap in CDC SVI or ADI via --ses-file if preferred._"]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("CI = %+.4f | wrote %s and %s", ci, OUT_MD, FIG)
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
