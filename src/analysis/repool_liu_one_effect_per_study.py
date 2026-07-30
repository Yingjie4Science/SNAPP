#!/usr/bin/env python3
"""Re-pool one NDVI-depression estimate per independent Liu et al. cohort.

This is a transparent robustness check, not a replacement for Liu et al.'s
published OR=0.931. The source values are transcribed from Liu et al. (2023)
Figure 4. A prespecified outcome hierarchy retains one estimate per cohort:
diagnosed depression where available, otherwise the study's sole validated
instrument. For Gonzales, the direct NDVI exposure is retained.

The script applies a DerSimonian-Laird random-effects model on log odds ratios,
matching the simple random-effects convention used for a feasible sensitivity
check. With only summary estimates, it cannot model within-study outcome
correlations or reproduce covariate adjustments.
"""

import csv
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT = BASE_DIR / "config" / "liu_2023_ndvi_depression_effects.csv"
OUT_CSV = BASE_DIR / "results" / "summaries" / "liu_one_effect_per_study.csv"
OUT_MD = BASE_DIR / "results" / "summaries" / "liu_one_effect_per_study.md"


def load_selected(path):
    rows = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            if row["selected_one_per_study"] != "1":
                continue
            estimate = float(row["or"])
            low = float(row["ci_low"])
            high = float(row["ci_high"])
            if not (0 < low <= estimate <= high):
                raise ValueError(f"Invalid OR interval: {row}")
            log_or = math.log(estimate)
            se = (math.log(high) - math.log(low)) / (2 * 1.96)
            rows.append({**row, "log_or": log_or, "se": se})
    studies = [r["study"] for r in rows]
    if len(studies) != len(set(studies)):
        raise ValueError("Selection must contain exactly one estimate per study.")
    return rows


def dersimonian_laird(rows):
    fixed_weights = [1 / r["se"] ** 2 for r in rows]
    fixed_mean = sum(w * r["log_or"] for w, r in zip(fixed_weights, rows)) / sum(fixed_weights)
    q = sum(w * (r["log_or"] - fixed_mean) ** 2 for w, r in zip(fixed_weights, rows))
    df = len(rows) - 1
    c = sum(fixed_weights) - sum(w * w for w in fixed_weights) / sum(fixed_weights)
    tau2 = max(0.0, (q - df) / c)
    random_weights = [1 / (r["se"] ** 2 + tau2) for r in rows]
    pooled = sum(w * r["log_or"] for w, r in zip(random_weights, rows)) / sum(random_weights)
    pooled_se = math.sqrt(1 / sum(random_weights))
    i2 = max(0.0, (q - df) / q) * 100 if q > 0 else 0.0
    return {
        "n_studies": len(rows),
        "pooled_or": math.exp(pooled),
        "ci_low": math.exp(pooled - 1.96 * pooled_se),
        "ci_high": math.exp(pooled + 1.96 * pooled_se),
        "tau2_log_or": tau2,
        "q": q,
        "df": df,
        "i2_percent": i2,
        "weights": random_weights,
    }


def main():
    rows = load_selected(INPUT)
    result = dersimonian_laird(rows)
    total_weight = sum(result["weights"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        fields = ["study", "effect_id", "outcome", "or", "ci_low", "ci_high",
                  "random_effect_weight_percent", "selection_reason"]
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row, weight in zip(rows, result["weights"]):
            writer.writerow({
                **{key: row[key] for key in fields if key != "random_effect_weight_percent"},
                "random_effect_weight_percent": f"{100 * weight / total_weight:.2f}",
            })

    md = [
        "# Liu et al. one-effect-per-study robustness check",
        "",
        "## Decision",
        "",
        "The published Liu et al. pooled OR **0.931 (95% CI 0.887–0.977)** remains "
        "the primary effect-size anchor. This analysis is a sensitivity check that "
        "prevents cohorts with multiple correlated outcomes from receiving multiple rows.",
        "",
        "A prespecified hierarchy retained diagnosed depression where available; "
        "otherwise the cohort's sole validated depression instrument was used. For "
        "Gonzales, the direct NDVI exposure was retained.",
        "",
        "## Result",
        "",
        f"- Studies: **{result['n_studies']}**",
        f"- DerSimonian–Laird pooled OR: **{result['pooled_or']:.3f}** "
        f"(95% CI {result['ci_low']:.3f}–{result['ci_high']:.3f})",
        f"- I²: **{result['i2_percent']:.1f}%**",
        f"- τ² on log-OR scale: **{result['tau2_log_or']:.5f}**",
        "",
        "## Interpretation and limits",
        "",
        "This check uses values transcribed from Liu et al. Figure 4. It does not "
        "replace a study-author reanalysis, cannot account for covariate differences, "
        "and uses a simple random-effects estimator. It should be reported alongside, "
        "not instead of, the published estimate.",
        "",
        "## To-do",
        "",
        "- Independently verify every transcribed coefficient against the Liu supplement.",
        "- Confirm which Perry and Abraham outcomes Liu treated as NDVI estimates.",
        "- If this sensitivity materially changes U.S. results, repeat with a multilevel "
        "or robust-variance meta-analysis.",
    ]
    OUT_MD.write_text("\n".join(md) + "\n")
    print(f"OR {result['pooled_or']:.3f} ({result['ci_low']:.3f}, {result['ci_high']:.3f}); "
          f"I2={result['i2_percent']:.1f}%")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
