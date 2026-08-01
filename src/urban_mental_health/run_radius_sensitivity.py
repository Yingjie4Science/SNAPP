#!/usr/bin/env python3
"""Run the SF uniform +0.05 scenario at alternative exposure radii.

The Liu et al. evidence combines neighborhood buffers spanning roughly
250-1000 m. This one-way sensitivity analysis holds population, prevalence,
effect size, cost, and the greening raster fixed while varying only the InVEST
search radius.
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model  # noqa: E402
from run_sensitivity import total_preventable_cases  # noqa: E402

LOGGER = logging.getLogger("radius_sensitivity")
RADII_M = (250, 300, 500, 1000)
WORKSPACES = run_model.RUNS / "radius_sensitivity"
OUT_CSV = run_model.RESULTS_SUMMARIES / "radius_sensitivity.csv"
OUT_MD = run_model.RESULTS_SUMMARIES / "radius_sensitivity.md"
FIG = run_model.RESULTS_FIGURES / "radius_sensitivity.png"


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model = run_model.load_model()
    base = run_model.build_args()
    adult_population = float(
        run_model.CFG.get("context", {}).get("population_adult", 716727))
    cost_rate = float(base.get("health_cost_rate", 0))
    rows = []
    for radius in RADII_M:
        suffix = f"radius_{radius}m"
        workspace = WORKSPACES / suffix
        args = dict(base)
        args["workspace_dir"] = str(workspace)
        args["results_suffix"] = suffix
        args["search_radius"] = float(radius)
        warnings = model.validate(args)
        for keys, message in warnings:
            LOGGER.warning("%s: %s", keys, message)
        model.MODEL_SPEC.execute(args, create_logfile=True)
        cases = total_preventable_cases(workspace, suffix)
        rows.append({
            "radius_m": radius,
            "preventable_cases": cases,
            "preventable_per_1000_adults": 1000 * cases / adult_population,
            "preventable_cost_usd": cases * cost_rate,
            "relative_to_300m": None,
        })
    reference = next(row["preventable_cases"] for row in rows
                     if row["radius_m"] == 300)
    for row in rows:
        row["relative_to_300m"] = row["preventable_cases"] / reference

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **row,
                "preventable_cases": f"{row['preventable_cases']:.1f}",
                "preventable_per_1000_adults":
                    f"{row['preventable_per_1000_adults']:.3f}",
                "preventable_cost_usd": f"{row['preventable_cost_usd']:.0f}",
                "relative_to_300m": f"{row['relative_to_300m']:.4f}",
            })

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    ax.plot([row["radius_m"] for row in rows],
            [row["preventable_cases"] for row in rows],
            marker="o", color="#2c7fb8")
    ax.axvline(300, color="0.5", linestyle="--", linewidth=1)
    ax.set(xlabel="Neighborhood exposure radius (m)",
           ylabel="Preventable depression cases / year",
           title="Radius sensitivity: uniform +0.05 NDVI scenario")
    ax.grid(alpha=0.2)
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=220, bbox_inches="tight")
    plt.close(fig)

    lines = [
        "# Exposure-radius sensitivity", "",
        "All rows use the calibrated SF adult population, the uniform +0.05 "
        "NDVI scenario, and the same epidemiologic and cost assumptions. Only "
        "the neighborhood averaging radius changes.", "",
        "| Radius (m) | Preventable cases/year | Cases/1,000 adults | "
        "Relative to 300 m |",
        "|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['radius_m']} | {row['preventable_cases']:,.1f} | "
            f"{row['preventable_per_1000_adults']:.3f} | "
            f"{row['relative_to_300m']:.3f} |")
    lines += [
        "", f"![Radius sensitivity](../figures/{FIG.name})",
        "<sub>Figure. One-way sensitivity of the uniform +0.05 NDVI scenario "
        "to the residential greenness averaging radius.</sub>", "",
        "Interpretation: this is a model-structure sensitivity, not an "
        "independent epidemiologic confidence interval. The 300 m result remains "
        "the primary specification.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote %s, %s, and %s", OUT_CSV, OUT_MD, FIG)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    main()
