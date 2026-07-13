# Exposure-response: effect size and exposure radius

This documents two modelling choices reviewers will scrutinise: (1) the greenness
effect size and the fact that it is an **odds ratio converted to a risk ratio**,
and (2) why we keep a **300 m** exposure radius.

## Source

Liu, Z. et al. (2023). *Green space exposure on depression and anxiety outcomes:
a meta-analysis.* **Environmental Research 231:116303.**
DOI [10.1016/j.envres.2023.116303](https://doi.org/10.1016/j.envres.2023.116303),
PMID 37268208.

Pooled association for depression: a **0.1-unit increase in NDVI** is linked to
lower odds of depression, **merged OR = 0.931 (95% CI 0.887–0.977)**. (The same
paper reports OR 0.963 per 10% green-space area, and a non-significant anxiety
estimate; we use the NDVI depression figure.)

## The metric: odds ratio vs risk ratio

The published 0.931 is an **odds ratio (OR)**. The InVEST Urban Mental Health
model applies `effect_size` as a **risk ratio (RR)** — it computes

```
preventable_cases = (1 − exp( ln(effect_size) · 10 · ΔNDVI )) · baseline_cases
```

so `effect_size` is a per-0.1-NDVI multiplier on **risk**. Depression is common
(~20% prevalence), and for common outcomes the OR is further from 1 than the RR.
Using the OR directly therefore **overstates** the protective effect and inflates
preventable cases.

### Conversion (Zhang & Yu 1998)

```
RR = OR / (1 − p0 + p0 · OR)
```

where `p0` is the baseline risk in the reference (least-green) group, approximated
by the population prevalence of depression. We use **p0 = 0.20** (US adult
depression prevalence, order-of-magnitude from CDC PLACES). The result is
insensitive to p0 across the plausible range:

| p0 | RR (from OR 0.931) |
|---|---|
| 0.15 | 0.941 |
| 0.20 | 0.944 |
| 0.25 | 0.947 |

Converted values used in the pipeline (p0 = 0.20):

| quantity | published OR | **RR used** |
|---|---|---|
| central | 0.931 | **0.944** |
| low bound (more protective) | 0.887 | **0.908** |
| high bound (least protective) | 0.977 | **0.982** |

Recompute anytime with `python src/inputs/effect_size.py --or 0.931 --p0 0.20`.

### Why this matters numerically

In the model's small-ΔNDVI regime, preventable cases scale roughly with
`−ln(effect_size)`. Because `ln(0.931) ≈ −0.0715` but `ln(0.944) ≈ −0.0576`,
using the OR instead of the RR overstates preventable cases by **~20–24%** — the
same order of magnitude as the all-ages-vs-adults population issue. Both
corrections are now applied.

### Where it's wired

- `config.yaml → model.effect_size / _low / _high` hold the **RR** values; the raw
  ORs and `baseline_risk_p0` are kept alongside for provenance.
- `src/inputs/effect_size.py` — the OR→RR converter (and CLI).
- `run_model.py`, `run_sensitivity.py`, `run_city.py` all consume the RR.

## The exposure radius: why 300 m

InVEST averages NDVI within `search_radius` of each populated pixel as the
greenness-exposure metric. Ideally this matches the buffer at which the effect
size was estimated.

The Liu et al. estimate is a **meta-analysis pooling primary studies that used a
range of buffers** (commonly 250 m, 300 m, 500 m, 1000 m); the pooled OR is
expressed *per 0.1 NDVI* and is not tied to a single distance. There is therefore
no single "correct" radius to match. We keep **300 m** because:

- it sits centrally within the 250–500 m buffers most common in the pooled
  residential-greenness literature;
- 300 m is the distance repeatedly used in urban mental-health exposure work and
  is the scale the InVEST model documentation itself cites for mental health;
- results are only weakly sensitive to radius within 250–500 m once NDVI is
  resolved at 30 m (Landsat), the resolution we use.

We deliberately do **not** adopt a larger radius (e.g. 1 km) because that would
average away the within-neighbourhood greenness gradient that the intervention
scenarios act on. If a future single-buffer effect size is adopted, set
`search_radius_m` in `config.yaml` to that buffer and note it here.

*Contrast:* the sister hypertension pipeline (Kula, `snapp_health`) uses a single
500 m buffer because it draws buffer-specific ORs (Bu et al. 2024); our pooled,
buffer-agnostic OR does not compel that choice.
