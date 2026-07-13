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
OUT_METRICS = RESULTS / "summaries" / "equity_metrics.csv"
FIG = RESULTS / "figures" / "equity_concentration_curves.png"
INCOME_VAR, POP_VAR = "B19013_001E", "B01003_001E"
SVI_URL = ("https://onemap.cdc.gov/onemapservices/rest/services/SVI/"
           "CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2/query")


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


def fetch_svi(state: str, county: str) -> dict:
    """GEOID -> 2022 CDC/ATSDR overall SVI percentile (RPL_THEMES).

    Higher values mean greater social vulnerability.  The official national
    tract feature service is queried only for the selected county, so this
    avoids a large local download and preserves leading-zero GEOIDs.
    """
    import requests
    params = {
        "where": f"ST='{state}' AND STCNTY='{state}{county}'",
        "outFields": "FIPS,RPL_THEMES",
        "returnGeometry": "false",
        "f": "json",
    }
    r = requests.get(SVI_URL, params=params, timeout=120)
    try:
        payload = r.json()
    except ValueError:
        sys.exit(f"CDC SVI request returned non-JSON (HTTP {r.status_code}).")
    if r.status_code != 200 or payload.get("error"):
        sys.exit(f"CDC SVI request failed: {payload.get('error', r.text[:300])}")
    out = {}
    for feature in payload.get("features", []):
        attrs = feature.get("attributes", {})
        try:
            svi = float(attrs["RPL_THEMES"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= svi <= 1:
            out[str(attrs.get("FIPS", "")).zfill(11)] = svi
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


def load_svi_file(path: Path) -> dict:
    """Read an SVI CSV with FIPS and RPL_THEMES columns."""
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            try:
                value = float(row["RPL_THEMES"])
                geoid = str(row["FIPS"]).zfill(11)
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= value <= 1:
                out[geoid] = value
    return out


def interpretation(ci: float, measure: str) -> str:
    if abs(ci) <= 0.02:
        return "no material gradient detected"
    if measure == "income":
        return ("benefits concentrate in lower-income neighborhoods (equity-promoting)"
                if ci < 0 else "benefits concentrate in higher-income neighborhoods (pro-rich)")
    return ("benefits concentrate in less socially vulnerable neighborhoods (equity concern)"
            if ci < 0 else "benefits concentrate in more socially vulnerable neighborhoods (equity-promoting)")


def analyse_measure(name, rank, cases, pop, rate, np):
    ci, cx, cy = concentration_index(rate, pop, rank)
    order = np.argsort(rank)
    dec_rows = []
    for decile, ix in enumerate(np.array_split(order, 10), 1):
        dec_rows.append((decile, rank[ix].mean(), 1000 * rate[ix].mean(),
                         100 * cases[ix].sum() / cases.sum()))
    return {"name": name, "ci": ci, "cx": cx, "cy": cy, "deciles": dec_rows,
            "interpretation": interpretation(ci, name)}


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
    ap.add_argument("--svi-file", type=Path, help="Local CDC SVI CSV (FIPS,RPL_THEMES).")
    ap.add_argument("--skip-svi", action="store_true", help="Run the income analysis only.")
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
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)

    ses = (load_ses_file(cli.ses_file) if cli.ses_file else
           fetch_acs(cli.state, cli.county, cli.acs_year, cli.api_key))
    svi = {} if cli.skip_svi else (load_svi_file(cli.svi_file) if cli.svi_file else
                                    fetch_svi(cli.state, cli.county))
    LOGGER.info("Income records: %d | SVI records: %d", len(ses), len(svi))

    rows = []
    for _, r in gdf.iterrows():
        geoid = r["GEOID"]
        if geoid in ses and r["sum_cases"] is not None:
            income, pop = ses[geoid]
            if pop > 0:
                rows.append((geoid, float(r["sum_cases"]), income, pop,
                             float(r["sum_cases"]) / pop, svi.get(geoid)))
    if len(rows) < 5:
        sys.exit(f"Only {len(rows)} tracts matched income data — cannot compute a stable index.")

    cases = np.array([x[1] for x in rows]); income = np.array([x[2] for x in rows])
    pop = np.array([x[3] for x in rows]); rate = np.array([x[4] for x in rows])
    income_result = analyse_measure("income", income, cases, pop, rate, np)
    results = [income_result]
    svi_rows = [x for x in rows if x[5] is not None]
    if svi_rows:
        s_cases = np.array([x[1] for x in svi_rows]); s_pop = np.array([x[3] for x in svi_rows])
        s_rate = np.array([x[4] for x in svi_rows]); s_rank = np.array([x[5] for x in svi_rows])
        results.append(analyse_measure("svi", s_rank, s_cases, s_pop, s_rate, np))

    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    ax.plot([0, 1], [0, 1], "--", color="0.6", label="line of equality")
    labels = {"income": "Income rank (low → high)", "svi": "SVI rank (low → high vulnerability)"}
    colors = {"income": "#2c7fb8", "svi": "#d95f02"}
    for result in results:
        ax.plot(result["cx"], result["cy"], color=colors[result["name"]], lw=2,
                label=f"{labels[result['name']]} (CI {result['ci']:+.3f})")
    ax.set_xlabel("Cumulative share of population (ranked as labeled)")
    ax.set_ylabel("Cumulative share of preventable cases")
    ax.set_title("Equity of greening benefit")
    ax.legend(fontsize=8); ax.set_aspect("equal")
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=200, bbox_inches="tight"); plt.close(fig)

    lines = ["# Equity analysis — who benefits from greening", "",
             f"_{len(rows)} tracts matched to ACS {cli.acs_year} income; "
             f"{len(svi_rows)} matched to CDC/ATSDR 2022 SVI._", "",
             "## Interpretation for decisions", "",
             f"- **Income:** CI **{income_result['ci']:+.3f}** — {income_result['interpretation']}."]
    svi_result = next((x for x in results if x["name"] == "svi"), None)
    if svi_result:
        lines.append(f"- **Social vulnerability (SVI):** CI **{svi_result['ci']:+.3f}** — "
                     f"{svi_result['interpretation']}.")
    lines += ["- **Bottom line:** the result describes the distribution of modeled benefit, "
              "not whether investments reach residents who need them most. Use it alongside "
              "project siting, community engagement, and anti-displacement safeguards.", "",
              "CI ranges from −1 to +1; values within ±0.02 are treated here as no material "
              "gradient. For income, negative means benefit is concentrated among lower-income "
              "tracts. For SVI, positive means benefit is concentrated among more vulnerable tracts.", "",
              f"![Concentration curves](../figures/{FIG.name})",
              "<sub>Curves above the diagonal indicate concentration among the lower end of the "
              "rank. For income that means lower income; for SVI that means lower vulnerability.</sub>", ""]
    for result in results:
        if result["name"] == "income":
            title, col = "## By income decile (1 = lowest income)", "mean tract income"
            fmt = lambda v: f"${v:,.0f}"
        else:
            title, col = "## By SVI decile (1 = least vulnerable)", "mean CDC SVI percentile"
            fmt = lambda v: f"{v:.3f}"
        lines += [title, "", f"| decile | {col} | preventable cases / 1,000 adults | % of total cases |",
                  "|---:|---:|---:|---:|"]
        for d, rank, r1000, share in result["deciles"]:
            lines.append(f"| {d} | {fmt(rank)} | {r1000:.1f} | {share:.1f}% |")
        lines.append("")
    lines += ["## Method and limits", "",
              "Population-weighted health concentration indices use preventable cases per adult, "
              "not total cases, so large tracts do not mechanically dominate. Income uses ACS 2023 "
              "median household income. CDC/ATSDR 2022 SVI uses 16 ACS social factors across four "
              "themes; its overall percentile (RPL_THEMES) is ranked nationally, so it is a broader "
              "deprivation lens than income alone.",
              "",
              "_Sources: Kakwani et al. (1997); CDC/ATSDR Social Vulnerability Index 2022; Wu et al. (2026)._"]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    with open(OUT_METRICS, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["measure", "rank_direction", "concentration_index",
                                                 "interpretation", "matched_tracts"])
        writer.writeheader()
        writer.writerow({"measure": "income", "rank_direction": "low income to high income",
                         "concentration_index": f"{income_result['ci']:.6f}",
                         "interpretation": income_result["interpretation"], "matched_tracts": len(rows)})
        if svi_result:
            writer.writerow({"measure": "svi", "rank_direction": "low vulnerability to high vulnerability",
                             "concentration_index": f"{svi_result['ci']:.6f}",
                             "interpretation": svi_result["interpretation"], "matched_tracts": len(svi_rows)})
    LOGGER.info("wrote %s, %s, and %s", OUT_MD, OUT_METRICS, FIG)
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()
