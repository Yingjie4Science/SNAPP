# Method upgrades adapted from Wu et al. (2026)

Four additions inspired by Wu, J., Ruan, J., Di, W., Ying, J., Zhou, J., Luo, Z.,
Rudan, I., & Song, P. (2026), *The global burden of hypertension preventable by
urban greenness* (*Nature Health*; see [references.md](references.md)). That paper
shares our core machinery — an exponential per-unit risk scaling
`RR_i = RR^(ΔNDVI/0.1)` (identical to InVEST's `1 − exp(ln(RR)·10·ΔNDVI)`) and an
OR→RR conversion at baseline prevalence — which independently validates our
approach. We adopted four refinements.

## 1. Best-potential greening scenario (within-city p95)

Wu et al. use a "best potential" target of the **95th percentile of city-level
NDVI within each country**. We adopt the idea but apply it **within each city**:
`make_ndvi_scenario.py --mode best_potential --percentile 95` raises every pixel
below the AOI's own 95th-percentile NDVI up to it.

Rationale for the change: greenness ceilings are climate- and region-bound. A
cross-city national target would ask a dry-climate city to reach a wet city's
greenness — physically implausible. Using each city's own distribution defines an
achievable, locally-fair "level up to our greenest neighborhoods" target. Wired
into `config.yaml` (`scenarios.best_potential`) and `run_pipeline.sh`.

## 2. Equity / concentration-index analysis

`equity_analysis.py` computes a **population-weighted health concentration index
(CI)** of the preventable depression *rate* against neighborhood socioeconomic
status (ACS median household income by default; pass `--ses-file` for CDC SVI or
ADI), plus a concentration curve and an income-decile table. CI < 0 means the
benefit concentrates in lower-income neighborhoods (equity-promoting); CI > 0 the
opposite. Method: Kakwani et al. (1997); framing after Wu et al. (2026), who report
socioeconomic (SDI) inequalities via the concentration index and slope index of
inequality.

## 3. PAF and crude rate — and why not full age-standardization

We now report the **population-attributable fraction (PAF)** and **preventable
cases per 1,000 adults** alongside counts (SF summary + national aggregator). Both
are independent of a place's size, so they are the right cross-county comparators
for the national scale-up.

We deliberately do **not** compute a full **age-standardized** preventable rate
(as Wu et al. do), because it is not feasible with our data:

- *Pros of age-standardization:* removes age-structure confounding, so counties
  with older vs. younger populations are directly comparable; matches the HIA
  convention.
- *Cons / blockers here:* it requires **5-year age-specific** depression prevalence
  and an **age-specific effect size**. CDC PLACES provides only a single adult
  (18+) depression rate per tract, and Liu et al. (2023) give a single pooled RR,
  not age-stratified. Fabricating an age split would add false precision.
- *Our resolution:* the **PAF** (dimensionless) and the **crude adult rate**
  achieve the comparability goal without age-specific inputs. If age-specific
  depression prevalence becomes available, age-standardization can be added later.

## 4. Uncertainty framed as a propagated 95% CI

The effect-size bounds we run (**RR 0.908–0.982**) are the Liu et al. (2023)
odds-ratio 95% CI converted to risk ratios, so the preventable-case values at
those bounds constitute a genuine **95% confidence interval**, now reported as
"cases (95% CI: low–high)". This is kept distinct from the **cost-per-case band**
($17k–$23k), which is a scenario range of cost-of-illness anchors, not a
statistical CI.

## What we keep that Wu et al. (2026) lack

Monetary valuation (societal cost per case), finer 30 m Landsat NDVI (vs 250 m
MODIS), and the dual counterfactual (marginal greening + total value of existing
greenness). These remain differentiators of this project.
