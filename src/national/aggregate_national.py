#!/usr/bin/env python3
"""
Aggregate the per-county national run into one table + headline totals.

After `run_national.sh` finishes, each county has its own workspace under
data/urban-mental-health/runs/national/<GEOID>/ with the model's per-tract
summary at output/*sum*<GEOID>*.csv. That CSV carries one row where
FID == "ALL" holding the county totals (total_cases, total_cost). This script
reads every county's ALL row, joins county names from config/regions.csv, and
writes:

  results/summaries/national_summary.csv    per-county: GEOID, name, tracts,
                                             preventable_cases, avoided_cost
  results/summaries/national_summary.md      headline national totals + top
                                             counties, and (if geopandas is
                                             installed) a rollup by metro area.

The core path uses only the standard library, so it runs without the geo stack.
Pass --metro-rollup (needs geopandas + data/national/counties.gpkg) to also
group results by metropolitan area, and --map for a per-county choropleth.

USAGE
    python src/national/aggregate_national.py
    python src/national/aggregate_national.py --metro-rollup --map
"""

import argparse
import csv
import glob
import logging
import os
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("aggregate_national")

BASE_DIR = Path(__file__).resolve().parents[2]
UMH = BASE_DIR / "data" / "urban-mental-health"
RUNS = UMH / "runs" / "national"
REGIONS_CSV = BASE_DIR / "config" / "regions.csv"
COUNTIES_GPKG = BASE_DIR / "data" / "national" / "counties.gpkg"
COST_FILE = UMH / "inputs" / "health_cost_rate.txt"
OUT_DIR = BASE_DIR / "results" / "summaries"
OUT_CSV = OUT_DIR / "national_summary.csv"
OUT_MD = OUT_DIR / "national_summary.md"
FIG = BASE_DIR / "results" / "figures" / "national_preventable_cases_map.png"


def read_county_names() -> dict:
    """GEOID -> county name from config/regions.csv (best-effort)."""
    names = {}
    if not REGIONS_CSV.exists():
        return names
    with open(REGIONS_CSV) as fh:
        for r in csv.DictReader(fh):
            gid = (r.get("GEOID") or "").strip()
            if gid and not gid.startswith("#"):
                names[gid] = (r.get("NAME") or "").strip()
    return names


def read_county_total(geoid: str):
    """Return (tracts, total_cases, total_cost) for one county, or None."""
    out = RUNS / geoid / "output"
    cands = sorted(glob.glob(str(out / f"*sum*{geoid}*.csv"))) \
        or sorted(glob.glob(str(out / "*sum*.csv")))
    if not cands:
        return None
    tracts, total_cases, total_cost = 0, None, None
    with open(cands[0]) as fh:
        for r in csv.DictReader(fh):
            if str(r.get("FID", "")).upper() == "ALL":
                total_cases = float(r["total_cases"]) if r.get("total_cases") else None
                total_cost = float(r["total_cost"]) if r.get("total_cost") else None
            elif r.get("sum_cases") not in (None, ""):
                tracts += 1
    return tracts, total_cases, total_cost


def collect() -> list:
    """One dict per county that produced output, sorted by cases desc."""
    if not RUNS.exists():
        raise SystemExit(f"No national runs at {RUNS}. Run run_national.sh first.")
    names = read_county_names()
    rows = []
    for geoid in sorted(os.listdir(RUNS)):
        if not (RUNS / geoid).is_dir():
            continue
        rec = read_county_total(geoid)
        if rec is None:
            LOGGER.warning("%s: no summary CSV yet — skipping.", geoid)
            continue
        tracts, cases, cost = rec
        # Adult population (from run_city) -> age-structure-independent rate per 1,000.
        adult_pop, rate = None, None
        pf = RUNS / geoid / "adult_pop.txt"
        if pf.exists():
            try:
                adult_pop = float(pf.read_text().strip())
                if adult_pop > 0 and cases is not None:
                    rate = 1000.0 * cases / adult_pop
            except ValueError:
                pass
        rows.append({
            "GEOID": geoid,
            "name": names.get(geoid, ""),
            "tracts": tracts,
            "preventable_cases": cases,
            "avoided_cost": cost,
            "adult_population": round(adult_pop) if adult_pop else "",
            "preventable_per_1000_adults": round(rate, 2) if rate is not None else "",
        })
    rows.sort(key=lambda d: (d["preventable_cases"] or 0), reverse=True)
    return rows


def write_csv(rows):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["GEOID", "name", "tracts",
                                           "preventable_cases", "avoided_cost",
                                           "adult_population", "preventable_per_1000_adults"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    LOGGER.info("Wrote %s (%d counties)", OUT_CSV, len(rows))


def metro_rollup(rows):
    """Group counties by metro via counties.gpkg; return list of md lines or None."""
    try:
        import geopandas as gpd
    except ImportError:
        LOGGER.warning("--metro-rollup needs geopandas; skipping.")
        return None
    if not COUNTIES_GPKG.exists():
        LOGGER.warning("counties.gpkg not found; skipping metro rollup.")
        return None
    gdf = gpd.read_file(COUNTIES_GPKG)
    if "metro_name" not in gdf.columns:
        LOGGER.warning("no metro_name column in counties.gpkg; skipping metro rollup.")
        return None
    meta = {str(r.GEOID): (r.get("metro_id", ""), r.get("metro_name", ""))
            for _, r in gdf.iterrows()}
    agg = {}
    for r in rows:
        _, mname = meta.get(r["GEOID"], ("", "(unmatched)"))
        a = agg.setdefault(mname or "(unmatched)", {"cases": 0.0, "cost": 0.0, "n": 0})
        a["cases"] += r["preventable_cases"] or 0
        a["cost"] += r["avoided_cost"] or 0
        a["n"] += 1
    top = sorted(agg.items(), key=lambda kv: kv[1]["cases"], reverse=True)[:20]
    lines = ["", "## Top 20 metros (by preventable cases/year)", "",
             "| metro | counties | preventable_cases | avoided_cost |",
             "|---|---:|---:|---:|"]
    for mname, a in top:
        lines.append(f"| {mname} | {a['n']} | {a['cases']:,.0f} | ${a['cost']:,.0f} |")
    return lines


def draw_map(rows):
    try:
        import geopandas as gpd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: F401
    except ImportError:
        LOGGER.warning("--map needs geopandas + matplotlib; skipping.")
        return None
    if not COUNTIES_GPKG.exists():
        LOGGER.warning("counties.gpkg not found; skipping map.")
        return None
    gdf = gpd.read_file(COUNTIES_GPKG)
    by_geoid = {r["GEOID"]: r["preventable_cases"] for r in rows}
    gdf["preventable_cases"] = gdf["GEOID"].astype(str).map(by_geoid)
    gdf = gdf.to_crs("EPSG:5070")
    ax = gdf.plot(column="preventable_cases", legend=True, cmap="YlGn",
                  edgecolor="0.8", linewidth=0.1, missing_kwds={"color": "0.9"})
    ax.set_axis_off()
    ax.set_title("Preventable depression cases/year by county (metro counties)")
    FIG.parent.mkdir(parents=True, exist_ok=True)
    ax.figure.savefig(FIG, dpi=200, bbox_inches="tight")
    LOGGER.info("Wrote map -> %s", FIG)
    return FIG


def main():
    ap = argparse.ArgumentParser(description="Aggregate national per-county runs.")
    ap.add_argument("--metro-rollup", action="store_true",
                    help="Also roll up by metro area (needs geopandas + counties.gpkg).")
    ap.add_argument("--map", action="store_true",
                    help="Also draw a per-county choropleth (needs geopandas + matplotlib).")
    cli = ap.parse_args()

    rows = collect()
    if not rows:
        raise SystemExit("No county outputs found — run run_national.sh first.")
    write_csv(rows)

    n = len(rows)
    tot_cases = sum(r["preventable_cases"] or 0 for r in rows)
    tot_cost = sum(r["avoided_cost"] or 0 for r in rows)
    rate = float(COST_FILE.read_text().strip()) if COST_FILE.exists() else None
    implied = (tot_cost / tot_cases) if tot_cases else None

    lines = [
        "# National results summary", "",
        f"_Generated {date.today().isoformat()} from {n} county runs "
        f"in `{RUNS.relative_to(BASE_DIR)}`._", "",
        "## Headline", "",
        f"- Counties with results: **{n}**",
        f"- Preventable depression cases/year (national): **{tot_cases:,.0f}**",
        f"- Avoided societal cost/year (national): **${tot_cost:,.0f}**",
    ]
    if implied and rate:
        ok = abs(implied - rate) / rate < 0.01
        lines.append(f"- Implied cost/case ${implied:,.0f} vs health_cost_rate "
                     f"${rate:,.0f} — {'OK (matches)' if ok else 'MISMATCH — investigate'}.")
    lines += [
        "- Population was adult-scaled in run_city.py (--adult-fraction, default 0.86), "
        "so totals are not the ~20%-overstated all-ages figure.",
        "", "## Top 20 counties (by preventable cases/year)", "",
        "| GEOID | county | tracts | preventable_cases | avoided_cost |",
        "|---|---|---:|---:|---:|",
    ]
    for r in rows[:20]:
        lines.append(f"| {r['GEOID']} | {r['name']} | {r['tracts']} | "
                     f"{(r['preventable_cases'] or 0):,.0f} | "
                     f"${(r['avoided_cost'] or 0):,.0f} |")

    if cli.metro_rollup:
        ml = metro_rollup(rows)
        if ml:
            lines += ml
    if cli.map:
        fig = draw_map(rows)
        if fig:
            lines += ["", f"![Preventable cases by county](../figures/{fig.name})"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote %s", OUT_MD)
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
