#!/usr/bin/env python3
"""Population-weighted national SVI equity analysis across modeled scenarios."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
SUMMARIES = BASE_DIR / "results/summaries"
FIGURES = BASE_DIR / "results/figures"
SCENARIOS = (
    "uniform_005",
    "proportional_10pct",
    "greenable_005",
    "best_potential_p95",
)


def weighted_rank(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    sorted_weights = weights[order]
    ranks = (np.cumsum(sorted_weights) - 0.5 * sorted_weights) / sorted_weights.sum()
    result = np.empty(len(values), dtype=float)
    result[order] = ranks
    return result


def metrics(frame: pd.DataFrame) -> tuple[float, float]:
    weights = frame["adult_population"].to_numpy(float)
    rate = (
        frame["preventable_cases"].to_numpy(float) / weights
    )
    rank = weighted_rank(frame["svi_2022"].to_numpy(float), weights)
    mean = np.average(rate, weights=weights)
    ci = 2 * np.average((rate - mean) * (rank - np.average(rank, weights=weights)),
                        weights=weights) / mean
    x = np.column_stack([np.ones(len(rank)), rank])
    root_w = np.sqrt(weights)
    slope = np.linalg.lstsq(x * root_w[:, None], rate * 1000 * root_w, rcond=None)[0][1]
    return float(ci), float(slope)


def bootstrap(frame: pd.DataFrame, draws: int, seed: int = 20260730) -> tuple:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        draw = frame.iloc[rng.integers(0, len(frame), len(frame))]
        values.append(metrics(draw))
    array = np.asarray(values)
    return (
        np.quantile(array[:, 0], [0.025, 0.975]),
        np.quantile(array[:, 1], [0.025, 0.975]),
    )


def scenario_path(label: str) -> Path:
    if label == "uniform_005":
        return SUMMARIES / "national_summary.csv"
    return SUMMARIES / f"national_summary_{label}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svi", type=Path,
                        default=BASE_DIR / "config/svi_county_2022.csv")
    parser.add_argument("--bootstrap", type=int, default=1000)
    cli = parser.parse_args()

    svi = pd.read_csv(cli.svi, dtype={"GEOID": str})
    svi["GEOID"] = svi["GEOID"].str.zfill(5)
    outputs = []
    decile_outputs = []
    merged_by_scenario = {}
    for number, label in enumerate(SCENARIOS):
        path = scenario_path(label)
        if not path.exists():
            continue
        results = pd.read_csv(path, dtype={"GEOID": str})
        results["GEOID"] = results["GEOID"].str.zfill(5)
        frame = results.merge(svi[["GEOID", "svi_2022"]], on="GEOID", how="left",
                              validate="one_to_one")
        frame = frame[
            frame["adult_population"].gt(0)
            & frame["preventable_cases"].notna()
            & frame["svi_2022"].between(0, 1)
        ].copy()
        if len(frame) != len(results):
            raise SystemExit(
                f"{label}: only {len(frame)}/{len(results)} counties have complete SVI/results"
            )
        ci, sii = metrics(frame)
        ci_interval, sii_interval = bootstrap(frame, cli.bootstrap, seed=20260730 + number)
        outputs.append({
            "scenario": label,
            "counties": len(frame),
            "concentration_index": ci,
            "ci_low": ci_interval[0],
            "ci_high": ci_interval[1],
            "sii_cases_per_1000": sii,
            "sii_low": sii_interval[0],
            "sii_high": sii_interval[1],
        })
        weights = frame["adult_population"].to_numpy(float)
        frame["svi_population_rank"] = weighted_rank(
            frame["svi_2022"].to_numpy(float), weights
        )
        frame["svi_decile"] = np.minimum(
            10, np.floor(frame["svi_population_rank"] * 10).astype(int) + 1
        )
        frame["rate_per_1000"] = (
            1000 * frame["preventable_cases"] / frame["adult_population"]
        )
        for decile, group in frame.groupby("svi_decile"):
            decile_outputs.append({
                "scenario": label,
                "svi_decile": int(decile),
                "adult_population": group["adult_population"].sum(),
                "mean_svi": np.average(
                    group["svi_2022"], weights=group["adult_population"]
                ),
                "preventable_cases": group["preventable_cases"].sum(),
                "preventable_per_1000_adults": (
                    1000 * group["preventable_cases"].sum()
                    / group["adult_population"].sum()
                ),
            })
        merged_by_scenario[label] = frame

    if not outputs:
        raise SystemExit("No complete national scenario summaries found.")
    metrics_frame = pd.DataFrame(outputs)
    deciles = pd.DataFrame(decile_outputs)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    metrics_frame.to_csv(SUMMARIES / "national_equity_svi_metrics.csv", index=False)
    deciles.to_csv(SUMMARIES / "national_equity_svi_deciles.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))
    x = np.arange(len(metrics_frame))
    left.errorbar(
        x,
        metrics_frame["concentration_index"],
        yerr=np.vstack([
            metrics_frame["concentration_index"] - metrics_frame["ci_low"],
            metrics_frame["ci_high"] - metrics_frame["concentration_index"],
        ]),
        fmt="o",
        capsize=3,
        color="#2c7fb8",
    )
    left.axhline(0, color="0.5", linewidth=1)
    left.set(
        xticks=x,
        xticklabels=metrics_frame["scenario"].str.replace("_", " "),
        ylabel="SVI concentration index",
        title="Relative inequality",
    )
    left.tick_params(axis="x", rotation=30)
    for label, group in deciles.groupby("scenario"):
        right.plot(
            group["svi_decile"],
            group["preventable_per_1000_adults"],
            marker="o",
            label=label.replace("_", " "),
        )
    right.set(
        xlabel="SVI population decile (10 = most vulnerable)",
        ylabel="Preventable cases / 1,000 adults",
        title="Absolute benefit gradient",
    )
    right.legend(fontsize=7)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig_path = FIGURES / "national_equity_svi.png"
    fig.savefig(fig_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    lines = [
        "# National SVI equity analysis",
        "",
        "County-level benefits are divided by ACS 2023 adult population and ranked "
        "by the official CDC/ATSDR 2022 national county SVI percentile. Positive "
        "concentration indices and SII slopes mean greater modeled benefit in more "
        "socially vulnerable counties; negative values indicate under-serving.",
        "",
        "| Scenario | Counties | SVI CI (95% bootstrap interval) | "
        "SII cases/1,000 (95% interval) |",
        "|---|---:|---:|---:|",
    ]
    for row in outputs:
        lines.append(
            f"| {row['scenario'].replace('_', ' ')} | {row['counties']} | "
            f"{row['concentration_index']:+.3f} "
            f"({row['ci_low']:+.3f}, {row['ci_high']:+.3f}) | "
            f"{row['sii_cases_per_1000']:+.3f} "
            f"({row['sii_low']:+.3f}, {row['sii_high']:+.3f}) |"
        )
    lines += [
        "",
        f"![National SVI equity](../figures/{fig_path.name})",
        "<sub>Figure. Population-weighted relative and absolute SVI gradients "
        "across national greening scenarios. Error bars are 95% county-bootstrap "
        "intervals.</sub>",
        "",
        "Interpretation is distributional, not causal. County-level SVI masks "
        "within-county inequity, and bootstrap intervals capture county sampling "
        "variation rather than epidemiologic, exposure, or cost uncertainty.",
    ]
    (SUMMARIES / "national_equity_svi.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
