#!/usr/bin/env python3
"""Summarize national uniform-scenario exposure-radius sensitivity."""

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
SUMMARIES = BASE_DIR / "results/summaries"
FIGURES = BASE_DIR / "results/figures"
RADII = (250, 300, 500, 1000)


def main() -> None:
    rows = []
    for radius in RADII:
        path = (
            SUMMARIES / "national_summary.csv"
            if radius == 300
            else SUMMARIES / f"national_summary_uniform_005_radius_{radius}m.csv"
        )
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        rows.append({
            "radius_m": radius,
            "counties": len(frame),
            "adult_population": frame["adult_population"].sum(),
            "preventable_cases": frame["preventable_cases"].sum(),
            "preventable_cost_usd": frame["avoided_cost"].sum(),
        })
    if len(rows) != len(RADII):
        raise SystemExit(f"Expected {len(RADII)} radius summaries; found {len(rows)}.")
    table = pd.DataFrame(rows)
    reference = table.loc[table["radius_m"].eq(300), "preventable_cases"].iloc[0]
    table["preventable_per_1000_adults"] = (
        1000 * table["preventable_cases"] / table["adult_population"]
    )
    table["relative_to_300m"] = table["preventable_cases"] / reference
    table.to_csv(SUMMARIES / "national_radius_sensitivity.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    ax.plot(table["radius_m"], table["preventable_cases"], marker="o")
    ax.axvline(300, color="0.5", linestyle="--", linewidth=1)
    ax.set(
        xlabel="Exposure radius (m)",
        ylabel="Preventable cases / year",
        title="National radius sensitivity: uniform +0.05 NDVI",
    )
    ax.grid(alpha=0.2)
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure = FIGURES / "national_radius_sensitivity.png"
    fig.savefig(figure, dpi=220, bbox_inches="tight")
    plt.close(fig)
    lines = [
        "# National exposure-radius sensitivity",
        "",
        "| Radius (m) | Counties | Cases/year | Cases/1,000 adults | "
        "Relative to 300 m |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in table.to_dict("records"):
        lines.append(
            f"| {row['radius_m']} | {row['counties']} | "
            f"{row['preventable_cases']:,.0f} | "
            f"{row['preventable_per_1000_adults']:.3f} | "
            f"{row['relative_to_300m']:.3f} |"
        )
    lines += [
        "",
        f"![National radius sensitivity](../figures/{figure.name})",
        "<sub>Figure. One-way sensitivity of national modeled cases to the "
        "residential greenness averaging radius; all other inputs are fixed.</sub>",
    ]
    (SUMMARIES / "national_radius_sensitivity.md").write_text(
        "\n".join(lines) + "\n"
    )


if __name__ == "__main__":
    main()
