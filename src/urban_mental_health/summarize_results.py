#!/usr/bin/env python3
"""
Summarize + QA the Urban Mental Health model outputs into a readable report.

Reads the per-tract summary CSV the model writes
(workspace/output/preventable_cases_cost_sum_*.csv), computes totals and
per-tract stats, folds in the sensitivity grid if present, runs a few sanity
checks, and writes docs/results_summary.md. Optional --map draws a per-tract
choropleth (needs geopandas + matplotlib).

Core report uses only the standard library, so it runs even without the geo
stack. USAGE:
    python src/urban_mental_health/summarize_results.py
    python src/urban_mental_health/summarize_results.py --map
"""

import argparse
import csv
import glob
import logging
from datetime import date
from pathlib import Path
from statistics import mean, median

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("summarize_results")

BASE_DIR = Path(__file__).resolve().parents[2]
UMH = BASE_DIR / "data" / "urban-mental-health"
WORKSPACE = UMH / "workspace"
SENS = UMH / "workspace_sensitivity" / "sensitivity_summary.csv"
COST_FILE = UMH / "inputs" / "health_cost_rate.txt"
OUT_MD = BASE_DIR / "docs" / "results_summary.md"


def load_sum_csv():
    """Return (per_tract_cases[list], total_cases, total_cost, path)."""
    cands = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*sf_2024*.csv"))) \
        or sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.csv")))
    if not cands:
        return None, None, None, None
    path = cands[0]
    per_tract, total_cases, total_cost = [], None, None
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if str(r.get("FID", "")).upper() == "ALL":
                total_cases = float(r["total_cases"]) if r.get("total_cases") else None
                total_cost = float(r["total_cost"]) if r.get("total_cost") else None
            elif r.get("sum_cases") not in (None, ""):
                per_tract.append(float(r["sum_cases"]))
    return per_tract, total_cases, total_cost, path


def read_sensitivity():
    if not SENS.exists():
        return None
    with open(SENS) as fh:
        return list(csv.DictReader(fh))


def draw_map():
    try:
        import geopandas as gpd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        LOGGER.warning("--map needs geopandas + matplotlib; skipping map.")
        return None
    gpkgs = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.gpkg")))
    if not gpkgs:
        LOGGER.warning("No summary gpkg found; skipping map.")
        return None
    gdf = gpd.read_file(gpkgs[0])
    ax = gdf.plot(column="sum_cases", legend=True, cmap="YlGn",
                  edgecolor="0.7", linewidth=0.2)
    ax.set_axis_off()
    ax.set_title("Preventable depression cases per tract (SF)")
    fig_path = BASE_DIR / "figures" / "preventable_cases_map.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    ax.figure.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(ax.figure)
    LOGGER.info("Wrote map -> %s", fig_path)
    return fig_path


def main():
    ap = argparse.ArgumentParser(description="Summarize + QA model outputs.")
    ap.add_argument("--map", action="store_true", help="Also draw a per-tract choropleth.")
    cli = ap.parse_args()

    per_tract, total_cases, total_cost, path = load_sum_csv()
    if path is None:
        raise SystemExit(f"No summary CSV in {WORKSPACE/'output'}. Run the model first.")

    rate = float(COST_FILE.read_text().strip()) if COST_FILE.exists() else None
    implied = (total_cost / total_cases) if (total_cost and total_cases) else None

    lines = [
        "# Model results summary (SF)", "",
        f"_Generated {date.today().isoformat()} from `{Path(path).name}`._", "",
        "## Headline", "",
        f"- Preventable depression cases/year: **{total_cases:,.0f}**" if total_cases else "- cases: n/a",
        f"- Avoided societal cost/year: **${total_cost:,.0f}**" if total_cost else "- cost: n/a",
        f"- Tracts analyzed: **{len(per_tract)}**",
    ]
    if per_tract:
        lines += [
            f"- Per-tract cases: mean {mean(per_tract):.1f}, median {median(per_tract):.1f}, "
            f"min {min(per_tract):.1f}, max {max(per_tract):.1f}",
        ]

    lines += ["", "## QA checks", ""]
    if implied and rate:
        ok = abs(implied - rate) / rate < 0.01
        lines.append(f"- Implied cost/case ${implied:,.0f} vs health_cost_rate ${rate:,.0f} "
                     f"— {'OK (matches)' if ok else 'MISMATCH — investigate'}.")
    lines.append("- Reminder: baseline cases should use ADULT population (prevalence is "
                 "adult); if population wasn't adult-scaled, totals are overstated ~20%.")
    lines.append("- Greening scenario and effect size are assumptions — read with the "
                 "sensitivity range below, not as point truth.")

    sens = read_sensitivity()
    if sens:
        lines += ["", "## Sensitivity (effect_size × cost)", "",
                  "| effect_size | preventable_cases | cost_low | cost_central | cost_high |",
                  "|---|---:|---:|---:|---:|"]
        for r in sens:
            lines.append(f"| {r.get('effect_size','?')} | "
                         f"{float(r.get('preventable_cases',0)):,.0f} | "
                         f"${float(r.get('cost_low_17000',0)):,.0f} | "
                         f"${float(r.get('cost_central_21280',0)):,.0f} | "
                         f"${float(r.get('cost_high_23000',0)):,.0f} |")

    if cli.map:
        fig = draw_map()
        if fig:
            lines += ["", f"![Preventable cases per tract](../figures/{fig.name})"]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote %s", OUT_MD)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
