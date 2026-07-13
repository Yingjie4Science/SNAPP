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


def _mpl():
    try:
        import geopandas as gpd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return gpd, plt
    except ImportError:
        LOGGER.warning("figures need geopandas + matplotlib; skipping.")
        return None, None


def draw_choropleth(workspace, column, title, cbar_label, out_name, cmap="YlGn"):
    """Titled choropleth with a labeled colorbar for one summary variable."""
    gpd, plt = _mpl()
    if gpd is None:
        return None
    gpkgs = sorted(glob.glob(str(workspace / "output" / "*sum*.gpkg")))
    if not gpkgs:
        LOGGER.warning("No summary gpkg in %s; skipping %s.", workspace, out_name)
        return None
    gdf = gpd.read_file(gpkgs[0])
    if column not in gdf.columns:
        LOGGER.warning("Column %s absent in %s; skipping %s.", column, gpkgs[0], out_name)
        return None
    fig, ax = plt.subplots(figsize=(6, 6))
    gdf.plot(column=column, legend=True, cmap=cmap, edgecolor="0.7", linewidth=0.2,
             ax=ax, legend_kwds={"label": cbar_label, "shrink": 0.6})
    ax.set_axis_off()
    ax.set_title(title, fontsize=11)
    out = RESULTS / "figures" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Wrote %s", out)
    return out


def draw_counterfactual_bar(marg_cases, tot_cases, marg_cost, tot_cost):
    """Grouped bar comparing the two counterfactuals (cases, cost annotated)."""
    _, plt = _mpl()
    if plt is None or marg_cases is None or tot_cases is None:
        return None
    fig, ax = plt.subplots(figsize=(5.2, 4))
    labels = ["Marginal greening\n(+0.05 NDVI)", "Existing greenness\n(vs NDVI=0)"]
    vals = [marg_cases, tot_cases]
    costs = [marg_cost, tot_cost]
    bars = ax.bar(labels, vals, color=["#2c7fb8", "#31a354"], width=0.6)
    ax.set_ylabel("Preventable depression cases / year")
    ax.set_title("Two counterfactuals: added vs. existing greenness")
    for b, v, c in zip(bars, vals, costs):
        lab = f"{v:,.0f} cases"
        if c:
            lab += f"\n${c/1e6:,.0f}M/yr"
        ax.text(b.get_x() + b.get_width() / 2, v, lab, ha="center", va="bottom", fontsize=9)
    ax.margins(y=0.18)
    out = RESULTS / "figures" / "counterfactual_comparison.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Wrote %s", out)
    return out


def _config_full():
    try:
        import yaml
        p = BASE_DIR / "config.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    except Exception:
        pass
    return {}


def baseline_check_lines(total_cases):
    """Reconcile the model's implied baseline vs. the census adult depression pool.

    The model's internal baseline can be backed out from preventable cases and the
    scenario dose: baseline = cases / (1 - RR^(10*delta)). Comparing it to the
    census-based pool (adults x prevalence) flags any population-input problem
    (all-ages vs adult-scaled, or bbox vs polygon clip).
    """
    cfg = _config_full()
    m, ctx, scen = cfg.get("model", {}), cfg.get("context", {}), cfg.get("scenario", {})
    rr = float(m.get("effect_size", 0.944))
    delta = float(scen.get("delta", 0.05))
    adult = ctx.get("population_adult")
    p0 = float(m.get("baseline_risk_p0", 0.204))
    if not (total_cases and adult):
        return []
    frac = 1.0 - rr ** (10 * delta)                 # per-case reduction at this dose
    if frac <= 0:
        return []
    implied_baseline = total_cases / frac
    census_pool = adult * p0
    ratio = implied_baseline / census_pool
    out = ["", "## Baseline & population check", "",
           f"- Marginal preventable fraction (model): **{100*frac:.2f}%** of baseline "
           f"cases at +{delta:g} NDVI (RR {rr:.3f}).",
           f"- Model-implied baseline depression cases: **{implied_baseline:,.0f}** "
           f"(= preventable / preventable-fraction).",
           f"- Census-based adult depression pool: **{census_pool:,.0f}** "
           f"({adult:,.0f} adults × {p0:.1%})."]
    if ratio > 1.15:
        out.append(f"- ⚠️ Model baseline is **{ratio:.2f}×** the census pool → the population "
                   f"raster likely sums ~{implied_baseline/p0:,.0f} (vs {adult:,.0f} adults). "
                   f"Check that population was adult-scaled AND clipped to the AOI polygon "
                   f"(not a bounding box). Fixing it scales the headline down by ~{100*(1-1/ratio):.0f}%.")
    elif ratio < 0.87:
        out.append(f"- ⚠️ Model baseline is only {ratio:.2f}× the census pool — investigate.")
    else:
        out.append(f"- ✅ Model baseline within {abs(1-ratio)*100:.0f}% of the census pool — consistent.")
    return out


def draw_sensitivity_range():
    """Avoided cost per effect_size, with the cost-band as error bars (range plot)."""
    _, plt = _mpl()
    if plt is None or not SENS.exists():
        return None
    rows = list(csv.DictReader(open(SENS)))
    if not rows:
        return None
    def g(r, k):
        return float(r.get(k, 0) or 0)
    labels = [r.get("effect_size", "?") for r in rows]
    cen = [g(r, "cost_central_21280") for r in rows]
    lo = [g(r, "cost_low_17000") for r in rows]
    hi = [g(r, "cost_high_23000") for r in rows]
    if not any(cen):
        LOGGER.warning("Sensitivity costs are all 0 (run the sed header fix); skipping range plot.")
        return None
    import numpy as np
    cen_a = np.array(cen)
    yerr = np.vstack([cen_a - np.array(lo), np.array(hi) - cen_a])
    fig, ax = plt.subplots(figsize=(5.6, 4))
    x = range(len(labels))
    ax.bar(x, cen_a / 1e6, color="#7fb8a4", width=0.55)
    ax.errorbar(x, cen_a / 1e6, yerr=yerr / 1e6, fmt="none", ecolor="0.25", capsize=5)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"RR {l}" for l in labels])
    ax.set_ylabel("Avoided societal cost ($M / yr)")
    ax.set_xlabel("Effect size (risk ratio per +0.1 NDVI)")
    ax.set_title("Avoided cost by effect size\n(error bars = $17k-$23k cost-per-case band)")
    out = RESULTS / "figures" / "sensitivity_range.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Wrote %s", out)
    return out


def draw_scatter():
    """Per-tract preventable cases vs baseline depression prevalence (where greening pays)."""
    gpd, plt = _mpl()
    if gpd is None:
        return None
    gpkgs = sorted(glob.glob(str(WORKSPACE / "output" / "*sum*.gpkg")))
    if not gpkgs:
        return None
    gdf = gpd.read_file(gpkgs[0])
    xcol = next((c for c in ("risk_rate", "DEPRESS", "prevalence") if c in gdf.columns), None)
    if xcol is None or "sum_cases" not in gdf.columns:
        LOGGER.warning("Scatter needs prevalence + sum_cases columns; skipping.")
        return None
    x = gdf[xcol].astype(float)
    if x.max() > 1.5:            # looks like a percent, not a fraction
        x = x / 100.0
    fig, ax = plt.subplots(figsize=(5.4, 4))
    ax.scatter(x * 100, gdf["sum_cases"].astype(float), s=18, alpha=0.6, color="#2c7fb8",
               edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Baseline depression prevalence (%)")
    ax.set_ylabel("Preventable cases / yr (tract)")
    ax.set_title("Where greening pays off: preventable cases vs. baseline prevalence")
    out = RESULTS / "figures" / "scatter_cases_vs_prevalence.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Wrote %s", out)
    return out


def literature_benchmark_lines(total_cases):
    """Benchmark the SF result against the greenness-depression literature."""
    m = _config_model()
    rr = float(m.get("effect_size", 0.944))
    per01 = 100 * (1 - rr)
    return [
        "", "## Literature benchmark", "",
        f"- **Greening magnitude.** Our +0.05 NDVI scenario is close to the Barcelona "
        f"\"Eixos Verds\" green-corridor plan, whose HIA modelled an average **+0.059 NDVI** — "
        f"so the dose is realistic, not arbitrary.",
        f"- **Method precedent.** A 2025 global study (J. Global Health) uses the same design "
        f"— scenario-based preventable depression burden from greenness via a pooled "
        f"meta-analytic OR and population-attributable fractions — so the approach is "
        f"established and publishable.",
        f"- **Effect magnitude.** Published per-0.1-NDVI depression reductions cluster around "
        f"**5-8%**; our risk-ratio gives **{per01:.1f}%** per 0.1 NDVI — at the conservative "
        f"end, as expected after the OR->RR correction (the higher figures use the OR directly).",
        f"- **Takeaway.** The preventable *fraction* is defensible and literature-consistent; "
        f"the absolute count depends on the population baseline (see check above).",
        "",
        "_Refs: Liu et al. 2023 Environ. Res. 231:116303; Barcelona Eixos Verds HIA "
        "(Mueller et al., Environ. Int. 2023); JOGH 2025;15:04280._",
    ]


def _config_context():
    try:
        import yaml
        p = BASE_DIR / "config.yaml"
        if p.exists():
            return (yaml.safe_load(p.read_text()) or {}).get("context", {})
    except Exception:
        pass
    return {}


def context_lines(total_cases, total_cost, tg_cases, tg_cost):
    """Intuitive reference numbers: cases vs population, cost vs GDP, vs baseline pool."""
    ctx = _config_context()
    if not ctx or not total_cases:
        return []
    city = ctx.get("city_name", "the city")
    pop = ctx.get("population_total")
    adult = ctx.get("population_adult")
    gdp = ctx.get("gdp_usd")
    p0 = float(_config_model().get("baseline_risk_p0", 0.204))
    out = ["", "## Context & reference numbers", "",
           f"Putting the {city} result in perspective:", ""]
    if pop:
        out.append(f"- Preventable cases are **{100*total_cases/pop:.2f}%** of total population "
                   f"({total_cases/pop*1000:.1f} per 1,000 residents).")
    if adult:
        pool = adult * p0
        line = (f"- Estimated adult depression pool ≈ **{pool:,.0f}** ({adult:,.0f} adults × "
                f"{p0:.1%}); marginal greening averts **{100*total_cases/pool:.1f}%** of it")
        if tg_cases:
            line += f", and existing greenness accounts for **{100*tg_cases/pool:.0f}%**."
        else:
            line += "."
        out.append(line)
    if gdp and total_cost:
        line = f"- Avoided societal cost is **{100*total_cost/gdp:.3f}%** of {city} GDP (~${gdp/1e9:,.0f}B)"
        if tg_cost:
            line += f"; existing-greenness value is **{100*tg_cost/gdp:.2f}%** of GDP."
        else:
            line += "."
        out.append(line)
    if pop and total_cost:
        out.append(f"- Avoided cost per resident: **${total_cost/pop:,.0f}/year**.")
    out.append("- (Population/GDP anchors live in config.yaml `context:` — update per city; "
               "GDP is an approximate BEA figure.)")
    return out


def main():
    ap = argparse.ArgumentParser(description="Summarize + QA model outputs.")
    ap.add_argument("--map", action="store_true",
                    help="Also render figures: per-tract maps (marginal cases, existing-"
                         "greenness cases, marginal cost) + a two-counterfactual bar chart.")
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

    # --- Context / reference numbers (cases vs population, cost vs GDP) ---
    lines += context_lines(total_cases, total_cost, tg_cases, tg_cost)
    lines += baseline_check_lines(total_cases)
    lines += literature_benchmark_lines(total_cases)

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
        figs = []
        # Map 1 — marginal greening scenario (per-tract preventable cases).
        figs.append((draw_choropleth(
            WORKSPACE, "sum_cases",
            "Marginal greening (+0.05 NDVI):\npreventable depression cases per tract, SF",
            "Preventable cases / yr", "map_marginal_cases.png"),
            "Preventable cases per tract — marginal greening (+0.05 NDVI)"))
        # Map 2 — total value of existing greenness (NDVI=0 counterfactual).
        figs.append((draw_choropleth(
            TOTAL_GREENNESS_WS, "sum_cases",
            "Existing greenness (vs NDVI=0):\ncases already averted per tract, SF",
            "Cases averted / yr", "map_existing_greenness_cases.png", cmap="Greens"),
            "Cases already averted by existing greenness per tract (NDVI=0 counterfactual)"))
        # Map 3 — avoided societal cost per tract (marginal).
        figs.append((draw_choropleth(
            WORKSPACE, "sum_cost",
            "Marginal greening: avoided societal cost per tract, SF",
            "Avoided cost / yr ($)", "map_marginal_cost.png", cmap="PuBuGn"),
            "Avoided societal cost per tract — marginal greening"))
        # Bar — the two counterfactuals side by side.
        figs.append((draw_counterfactual_bar(total_cases, tg_cases, total_cost, tg_cost),
                     "Two counterfactuals: added vs. existing greenness"))
        # Sensitivity range plot (effect size × cost band).
        figs.append((draw_sensitivity_range(),
                     "Avoided cost by effect size, with cost-per-case band as error bars"))
        # Scatter — where greening pays off (cases vs baseline prevalence).
        figs.append((draw_scatter(),
                     "Per-tract preventable cases vs. baseline depression prevalence"))

        embeds = [f'\n![{cap}](../figures/{fig.name})' for fig, cap in figs if fig]
        if embeds:
            lines += ["", "## Figures", ""] + embeds
            # (results_summary.md lives in results/summaries/; figures in results/figures/)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote %s", OUT_MD)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
