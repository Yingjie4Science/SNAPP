#!/usr/bin/env python3
"""
Generate publication-quality figures + tables for the manuscript (Nature Cities).

Reads the actual model outputs and inputs and writes:
  figures/manuscript/  Fig1_study_area.(pdf|png)      study-area / inputs (NDVI, prevalence, population)
                       Fig2_results_map.(pdf|png)      per-tract preventable cases (+ cost)
                       Fig3_scenario_comparison.(pdf|png)
                       Fig4_sensitivity.(pdf|png)
  tables/              Table1_data_sources.(csv|md)    inputs + provenance (static)
                       Table2_results_summary.(csv|md) totals + sensitivity range

Nature style: Arial, small type, colorblind-safe palettes, 88/180 mm widths,
editable-text vector PDF (fonttype 42) + 300 dpi PNG. Each figure is independent
and skips gracefully (with a note) if its inputs aren't present yet.

REQUIREMENTS  (conda env `snapp`): geopandas, rioxarray, rasterio, matplotlib, numpy, pandas
USAGE
    python src/urban_mental_health/make_manuscript_figures.py
    python src/urban_mental_health/make_manuscript_figures.py --scenario lulc_masked
"""

import argparse
import csv
import glob
import logging
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("make_figures")

BASE_DIR = Path(__file__).resolve().parents[2]
UMH = BASE_DIR / "data" / "urban-mental-health"
INPUTS = UMH / "inputs"
WORKSPACE = UMH / "workspace"
SCEN_CSV = UMH / "workspace_scenarios" / "scenario_comparison.csv"
SENS_CSV = UMH / "workspace_sensitivity" / "sensitivity_summary.csv"
FIGDIR = BASE_DIR / "figures" / "manuscript"
TABDIR = BASE_DIR / "tables"

MM = 1 / 25.4
SINGLE, DOUBLE = 88 * MM, 180 * MM   # Nature column widths

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
    "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 6,
    "axes.linewidth": 0.5, "savefig.dpi": 300, "figure.dpi": 150,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})


def save(fig, name):
    FIGDIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGDIR / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Wrote %s.{pdf,png}", FIGDIR / name)


def panel_label(ax, letter):
    ax.text(-0.05, 1.05, letter, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="top", ha="right")


def _raster(ax, path, cmap, label, title):
    import rioxarray
    da = rioxarray.open_rasterio(path, masked=True).squeeze()
    b = da.rio.bounds()  # (left, bottom, right, top)
    im = ax.imshow(da.values, extent=[b[0], b[2], b[1], b[3]], origin="upper",
                   cmap=cmap)
    ax.set_axis_off(); ax.set_title(title)
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label(label); cb.ax.tick_params(labelsize=6)
    cb.outline.set_linewidth(0.5)
    return da


def _choropleth(ax, gdf, col, cmap, label, title):
    gdf.plot(column=col, ax=ax, cmap=cmap, edgecolor="0.6", linewidth=0.15,
             legend=True, legend_kwds={"label": label, "shrink": 0.6})
    ax.set_axis_off(); ax.set_title(title)


# --------------------------------------------------------------------------
def fig1_study_area():
    import geopandas as gpd
    prev = INPUTS / "baseline_prevalence.gpkg"
    if not (INPUTS / "ndvi_base.tif").exists() or not prev.exists():
        LOGGER.warning("Fig1 skipped — need ndvi_base.tif + baseline_prevalence.gpkg."); return
    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE, DOUBLE / 2.7))
    _raster(axes[0], INPUTS / "ndvi_base.tif", "YlGn", "NDVI", "Baseline greenness (NDVI)")
    gdf = gpd.read_file(prev)
    _choropleth(axes[1], gdf, "risk_rate", "magma_r", "Depression prevalence",
                "Baseline depression prevalence")
    if (INPUTS / "population.tif").exists():
        _raster(axes[2], INPUTS / "population.tif", "cividis", "People per pixel",
                "Adult population")
    else:
        axes[2].set_axis_off()
    for ax, l in zip(axes, "abc"):
        panel_label(ax, l)
    save(fig, "Fig1_study_area")


def fig2_results_map(scenario_label):
    import geopandas as gpd
    gpkgs = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.gpkg")))
    if not gpkgs:
        LOGGER.warning("Fig2 skipped — no summary gpkg in workspace/output. Run the model."); return
    gdf = gpd.read_file(gpkgs[0])
    has_cost = "sum_cost" in gdf.columns and gdf["sum_cost"].notna().any()
    n = 2 if has_cost else 1
    fig, axes = plt.subplots(1, n, figsize=(DOUBLE if has_cost else SINGLE, SINGLE))
    axes = np.atleast_1d(axes)
    _choropleth(axes[0], gdf, "sum_cases", "YlGnBu",
                "Preventable cases yr$^{-1}$", "Preventable depression cases")
    panel_label(axes[0], "a")
    if has_cost:
        gdf["cost_k"] = gdf["sum_cost"] / 1e3
        _choropleth(axes[1], gdf, "cost_k", "YlOrRd",
                    "Avoided cost (US$ 000s yr$^{-1}$)", "Avoided societal cost")
        panel_label(axes[1], "b")
    save(fig, "Fig2_results_map")


def fig3_scenario_comparison():
    if not SCEN_CSV.exists():
        LOGGER.warning("Fig3 skipped — run run_scenarios.py first (%s).", SCEN_CSV); return
    rows = list(csv.DictReader(open(SCEN_CSV)))
    if not rows:
        LOGGER.warning("Fig3 skipped — empty scenario comparison."); return
    labels = [r["scenario"] for r in rows]
    cases = [float(r["preventable_cases"]) for r in rows]
    cost_col = [c for c in rows[0] if c.startswith("preventable_cost")][0]
    cost = [float(r[cost_col]) / 1e6 if r[cost_col] else 0 for r in rows]
    x = np.arange(len(labels))
    fig, ax1 = plt.subplots(figsize=(SINGLE, SINGLE * 0.8))
    b = ax1.bar(x - 0.2, cases, 0.4, color="#2c7fb8", label="Cases")
    ax1.set_ylabel("Preventable cases yr$^{-1}$")
    ax2 = ax1.twinx()
    ax2.bar(x + 0.2, cost, 0.4, color="#d95f0e", label="Cost")
    ax2.set_ylabel("Avoided cost (US$ M yr$^{-1}$)")
    ax2.spines["top"].set_visible(False)
    ax1.set_xticks(x); ax1.set_xticklabels(labels, rotation=20, ha="right")
    ax1.set_title("Preventable cases and cost by greening scenario")
    save(fig, "Fig3_scenario_comparison")


def fig4_sensitivity():
    if not SENS_CSV.exists():
        LOGGER.warning("Fig4 skipped — run run_sensitivity.py first (%s).", SENS_CSV); return
    rows = list(csv.DictReader(open(SENS_CSV)))
    cost_cols = [c for c in rows[0] if c.startswith("cost_")]
    es = [r["effect_size"] for r in rows]
    M = np.array([[float(r[c]) / 1e6 for c in cost_cols] for r in rows])
    fig, ax = plt.subplots(figsize=(SINGLE, SINGLE * 0.85))
    im = ax.imshow(M, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(cost_cols)))
    ax.set_xticklabels([c.replace("cost_", "").replace("_", "\n$") for c in cost_cols])
    ax.set_yticks(range(len(es))); ax.set_yticklabels(es)
    ax.set_xlabel("Societal cost per case"); ax.set_ylabel("Effect size (RR per +0.1 NDVI)")
    ax.set_title("Avoided cost (US$ M yr$^{-1}$)")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=6)
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02); cb.outline.set_linewidth(0.5)
    save(fig, "Fig4_sensitivity")


# --------------------------------------------------------------------------
def table1_data_sources():
    TABDIR.mkdir(parents=True, exist_ok=True)
    rows = [
        ("Greenness (NDVI)", "Landsat C2 L2, JJAS 90th percentile, 30 m", "USGS/GEE", "2024"),
        ("Greening scenarios", "LULC-masked / canopy-target / greenable", "NLCD Land Cover + TCC", "2021/2024"),
        ("AOI + population units", "Census tracts; WorldPop adult population 100 m", "Census TIGER; WorldPop R2025A", "2024"),
        ("Depression prevalence", "CDC PLACES crude prevalence (risk_rate)", "CDC PLACES", "2021"),
        ("Effect size", "RR 0.93 per +0.1 NDVI (0.887-0.977)", "Liu et al. 2023 (Environ. Res.)", "2023"),
        ("Societal cost / case", "US$21,280 (range 17,000-23,000)", "Greenberg 2018/2019; Konig 2019 meta-analysis", "2024 USD"),
        ("Model", "InVEST Urban Mental Health", "natcap.invest >=3.19", "-"),
    ]
    hdr = ["Input", "Description", "Source", "Year"]
    with open(TABDIR / "Table1_data_sources.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(hdr); w.writerows(rows)
    md = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
    md += ["| " + " | ".join(r) + " |" for r in rows]
    (TABDIR / "Table1_data_sources.md").write_text(
        "**Table 1.** Model inputs and data sources.\n\n" + "\n".join(md) + "\n")
    LOGGER.info("Wrote Table1_data_sources.{csv,md}")


def table2_results_summary():
    TABDIR.mkdir(parents=True, exist_ok=True)
    csvs = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.csv")))
    total_cases = total_cost = None
    if csvs:
        for r in csv.DictReader(open(csvs[0])):
            if str(r.get("FID", "")).upper() == "ALL":
                total_cases = float(r["total_cases"]) if r.get("total_cases") else None
                total_cost = float(r["total_cost"]) if r.get("total_cost") else None
    rows = [["Metric", "Value"]]
    if total_cases is not None:
        rows.append(["Preventable cases per year (central)", f"{total_cases:,.0f}"])
    if total_cost is not None:
        rows.append(["Avoided societal cost per year (central)", f"US${total_cost:,.0f}"])
    if SENS_CSV.exists():
        s = list(csv.DictReader(open(SENS_CSV)))
        cases = [float(r["preventable_cases"]) for r in s]
        rows.append(["Preventable cases range (effect-size sensitivity)",
                     f"{min(cases):,.0f} – {max(cases):,.0f}"])
    with open(TABDIR / "Table2_results_summary.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    md = ["| " + " | ".join(rows[0]) + " |", "|---|---|"]
    md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    (TABDIR / "Table2_results_summary.md").write_text(
        "**Table 2.** Summary of preventable depression burden, San Francisco.\n\n"
        + "\n".join(md) + "\n")
    LOGGER.info("Wrote Table2_results_summary.{csv,md}")


def main():
    ap = argparse.ArgumentParser(description="Manuscript figures + tables.")
    ap.add_argument("--scenario", default="sf_2024", help="results-map run label.")
    cli = ap.parse_args()
    for fn in (lambda: fig1_study_area(),
               lambda: fig2_results_map(cli.scenario),
               fig3_scenario_comparison, fig4_sensitivity,
               table1_data_sources, table2_results_summary):
        try:
            fn()
        except Exception as e:   # keep going; report which figure failed
            LOGGER.warning("step failed: %s", e)
    LOGGER.info("Figures -> %s ; tables -> %s", FIGDIR, TABDIR)


if __name__ == "__main__":
    main()
