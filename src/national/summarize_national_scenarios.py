#!/usr/bin/env python3
"""Create one comparison table and figure for national greening scenarios."""

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
SUMMARIES = BASE_DIR / "results/summaries"
FIGURES = BASE_DIR / "results/figures"
SCENARIOS = (
    ("uniform_005", "Uniform +0.05 NDVI", "national_summary.csv"),
    ("proportional_10pct", "Proportional +10% NDVI",
     "national_summary_proportional_10pct.csv"),
    ("greenable_005", "Greenable-only +0.05 NDVI",
     "national_summary_greenable_005.csv"),
    ("best_potential_p95", "Within-county p95 potential",
     "national_summary_best_potential_p95.csv"),
)


def main() -> None:
    rows = []
    for key, label, filename in SCENARIOS:
        frame = pd.read_csv(SUMMARIES / filename)
        rows.append({
            "scenario": key,
            "label": label,
            "counties": len(frame),
            "adult_population": frame["adult_population"].sum(),
            "preventable_cases": frame["preventable_cases"].sum(),
            "avoided_cost_usd": frame["avoided_cost"].sum(),
        })
    table = pd.DataFrame(rows)
    table["preventable_per_1000_adults"] = (
        1000 * table["preventable_cases"] / table["adult_population"]
    )
    reference = table.loc[
        table["scenario"].eq("uniform_005"), "preventable_cases"
    ].iloc[0]
    table["relative_to_uniform"] = table["preventable_cases"] / reference
    table.to_csv(SUMMARIES / "national_scenario_comparison.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ax.barh(table["label"], table["preventable_cases"], color="#2c7fb8")
    ax.invert_yaxis()
    ax.set(
        xlabel="Preventable depression cases / year",
        title="National comparison of greening scenarios",
    )
    ax.ticklabel_format(axis="x", style="plain")
    for index, value in enumerate(table["preventable_cases"]):
        ax.text(value, index, f" {value:,.0f}", va="center", fontsize=8)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure = FIGURES / "national_scenario_comparison.png"
    fig.savefig(figure, dpi=220, bbox_inches="tight")
    plt.close(fig)

    rules = {
        "uniform_005": "Raise every valid pixel by 0.05 NDVI, capped at 0.90.",
        "proportional_10pct": "Increase every valid pixel by 10%, capped at 0.90.",
        "greenable_005": "Add 0.05 only where baseline NDVI is below 0.60.",
        "best_potential_p95": "Raise lower pixels to each county's own p95 NDVI.",
    }
    lines = [
        "# National scenario comparison",
        "",
        "All scenarios use the same 1,167 counties, ACS 2023 adult population, "
        "PLACES prevalence, locked national p0/RR, 300 m exposure radius, and "
        "$21,280 societal cost per case.",
        "",
        f"![National scenario comparison](../figures/{figure.name})",
        "<sub>Figure. Annual modeled preventable depression cases under four "
        "national greening counterfactuals. The p95 scenario is an aspirational "
        "upper bound, not a feasible investment program.</sub>",
        "",
        "| Scenario | Spatial rule | Cases/year | Cases/1,000 adults | "
        "Avoided societal cost/year | Relative to uniform |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in table.to_dict("records"):
        lines.append(
            f"| {row['label']} | {rules[row['scenario']]} | "
            f"{row['preventable_cases']:,.0f} | "
            f"{row['preventable_per_1000_adults']:.2f} | "
            f"${row['avoided_cost_usd']:,.0f} | "
            f"{row['relative_to_uniform']:.2f} |"
        )
    lines += [
        "",
        "<sub>Table legend. Values are annual central estimates. All rows use "
        "218,643,229 ACS adults and exactly 1,167 counties. These scenarios differ "
        "in greening magnitude and feasibility, so they should not be ranked as "
        "equal-budget policy alternatives.</sub>",
    ]
    (SUMMARIES / "national_scenario_comparison.md").write_text(
        "\n".join(lines) + "\n"
    )


if __name__ == "__main__":
    main()
