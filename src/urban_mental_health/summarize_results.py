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
WORKSPACE = UMH / "runs" / "sf_baseline"                  # base model run
TOTAL_GREENNESS_WS = UMH / "runs" / "sf_total_greenness"  # existing-greenness run
RESULTS = BASE_DIR / "results"
SENS = RESULTS / "summaries" / "sensitivity_summary.csv"
COST_FILE = UMH / "inputs" / "health_cost_rate.txt"
OUT_MD = RESULTS / "summaries" / "results_summary.md"


def load_sum_csv(workspace: Path = WORKSPACE, suffix: str = "sf_2024"):
    """Return (per_tract_cases[list], total_cases, total_cost, path)."""
    cands = sorted(glob.glob(str(workspace / "output" / f"*sum*{suffix}*.csv"))) \
        or sorted(glob.glob(str(workspace / "output" / "*sum*.csv")))
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


def _config_model():
    try:
        import yaml
        p = BASE_DIR / "config.yaml"
        if p.exists():
            return (yaml.safe_load(p.read_text()) or {}).get("model", {})
    except Exception:
        pass
    return {}


def p0_sensitivity_lines(central_cases):
    """How the OR->RR conversion (and thus central cases) moves with baseline risk p0.

    Cases scale ~ -ln(RR) in the small-dNDVI regime, so we scale the model's
    central preventable_cases by ln(RR_p0)/ln(RR_used) to show robustness.
    """
    import math

    def or_to_rr(o, p0):
        return o / (1.0 - p0 + p0 * o)

    m = _config_model()
    or_c = float(m.get("effect_size_or", 0.931))
    p0_used = float(m.get("baseline_risk_p0", 0.20))
    rr_used = or_to_rr(or_c, p0_used)
    out = ["", "## p0 sensitivity (OR->RR conversion)", "",
           f"Baseline risk p0 used: **{p0_used:.3f}** (population-weighted PLACES "
           f"prevalence); central OR {or_c:.3f} -> RR {rr_used:.4f}. The RR is nearly "
           f"flat in p0, but preventable cases scale with -ln(RR), so they move "
           f"~±6% per 0.05 change in p0 — hence pinning p0 to the data (compute_p0.py):",
           "",
           "| p0 | RR | approx. preventable cases |", "|---:|---:|---:|"]
    for p in (0.10, 0.15, 0.20, 0.25, 0.30):
        rr = or_to_rr(or_c, p)
        cases = (central_cases * math.log(rr) / math.log(rr_used)) if (central_cases and rr_used != 1) else float("nan")
        mark = "  ← used" if abs(p - p0_used) < 1e-9 else ""
        out.append(f"| {p:.2f}{mark} | {rr:.4f} | {cases:,.0f} |")
    return out


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
    fig_path = RESULTS / "figures" / "preventable_cases_map.png"
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

    # --- Dual counterfactual: value of EXISTING greenness (baseline NDVI=0) ---
    tg_tract, tg_cases, tg_cost, tg_path = load_sum_csv(TOTAL_GREENNESS_WS, "sf_total_greenness")
    lines += ["", "## Two counterfactuals", ""]
    if tg_path and tg_cases:
        lines += [
            "Two distinct questions, reported side by side:",
            "",
            f"- **Marginal greening** (current NDVI -> +scenario): **{total_cases:,.0f}** "
            f"preventable cases/yr"
            + (f", **${total_cost:,.0f}**/yr." if total_cost else "."),
            f"- **Total value of existing greenness** (bare NDVI=0 -> current): "
            f"**{tg_cases:,.0f}** cases/yr already averted"
            + (f", **${tg_cost:,.0f}**/yr." if tg_cost else "."),
            "",
            "The first is the benefit of *adding* greenness (policy-relevant marginal "
            "effect); the second is an ecosystem-service accounting of greenness already "
            "present. The NDVI=0 figure extrapolates the exposure-response well beyond "
            "observed data, so treat it as an upper-bound accounting number, not a "
            "prediction of what removing all vegetation would do.",
        ]
    else:
        lines.append("_Existing-greenness (NDVI=0) run not found. Generate it with "
                     "`python src/urban_mental_health/run_model.py --total-greenness`._")

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

    lines += p0_sensitivity_lines(total_cases)

    if cli.map:
        fig = draw_map()
        if fig:
            lines += ["", f"![Preventable cases per tract](../figures/{fig.name})"]
            # (results_summary.md lives in results/summaries/; figure in results/figures/)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote %s", OUT_MD)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
