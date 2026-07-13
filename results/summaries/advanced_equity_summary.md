# Advanced equity analysis

## Decision finding

The analysis compares relative (concentration index) and absolute (slope index of inequality) distributions of modeled preventable depression rates, with 95% tract-bootstrap intervals. It also identifies spatially clustered priority tracts and supplies transparent scores for matched-budget health, equity, and balanced allocation scenarios.

## Primary distributional results: uniform +0.05 reference

| Equity lens | CI (95% CI) | SII cases / 1,000 adults (95% CI) | Interpretation |
|---|---:|---:|---|
| income | +0.016 (+0.007, +0.025) | +0.56 (+0.25, +0.85) | no material gradient |
| svi | -0.022 (-0.031, -0.011) | -0.75 (-1.08, -0.39) | vulnerability-under-serving |
| ice_income | +0.012 (+0.003, +0.020) | +0.41 (+0.10, +0.70) | no material gradient |

Global Moran's I for the equity-priority score: **+0.298** (k-nearest-neighbor diagnostic). Priority clusters are planning targets, not causal estimates.

![SVI inequality intervals](../figures/equity_svi_inequality_intervals.png)
<sub>Relative and absolute SVI inequality by scenario; error bars are 95% tract-bootstrap intervals.</sub>

![Equity-priority map](../figures/equity_priority_map.png)
<sub>Higher scores combine modeled cases per feasible NDVI increment, SVI, and low baseline greenness.</sub>

![Health–equity trade-off](../figures/equity_health_pareto.png)
<sub>Each point is a modeled scenario; vertical position indicates whether benefit is concentrated in higher-SVI tracts.</sub>

![Equity-priority spatial clusters](../figures/equity_priority_clusters.png)
<sub>Local spatial clusters of the equity-priority score; use as a screening map for place-based planning, not a causal inference map.</sub>

## Methods and limits

Income and ICE rank privilege upward; SVI, renter share, and minority share rank potential vulnerability upward. The SII is a population-weighted linear difference from the bottom to the top of a fractional rank. Bootstrap intervals reflect tract-sampling uncertainty only; they do not replace epidemiologic effect-size uncertainty. 2 tracts without valid SVI were excluded from SVI-ranked and equity-allocation scoring rather than imputed; 59 additional tracts had no feasible NDVI capacity and therefore received no allocation score. The renter/SVI safeguard flag is not a measure of observed displacement and should trigger community co-design and anti-displacement review.
