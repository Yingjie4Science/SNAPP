# San Francisco: health benefits of urban greenery

_Generated 2026-07-14._

This report estimates how much depression could be prevented — and how much money saved — by increasing greenery (street trees, parks, vegetation) across San Francisco. It combines satellite greenery (the NDVI index), local adult depression rates (CDC PLACES) and where people live (WorldPop) via the InVEST Urban Mental Health model. Key terms are defined in the glossary at the end.

## In brief

Adding a modest amount of greenery across San Francisco — a **+0.05 rise in the NDVI greenery index**, roughly the scale of Barcelona's green-corridor plan — could prevent about **4,867 cases of depression per year** (95% CI: 1,549–8,073), worth roughly **$104 million** in avoided societal cost. Separately, the greenery San Francisco *already has* is estimated to prevent about **21,321 cases per year** versus a bare city.

## Headline numbers

- **4,867** depression cases prevented per year (95% CI: 1,549–8,073) (from added greenery)
- **$103,573,424** avoided societal cost per year (95% CI: $33–$172M)
- Neighborhoods analyzed: **241** census tracts
- Per neighborhood: **20** cases prevented on average (range 1–65).

## Scenario comparison

The five investment scenarios use the same exposure-response, baseline depression, population, and societal-cost assumptions; they differ only in where and how much greening is allowed. The existing-greenness row is included for context, but it is an accounting counterfactual (today's greenness versus a bare city), not an investment option or a plausible removal forecast.

![Figure 1. Annual modeled prevented depression cases. Blue bars are alternative investment scenarios; the green bar is the existing-greenness accounting counterfactual. All bars use the same central health-effect and societal-cost assumptions. The green bar is not a project option or a forecast of vegetation removal.](../figures/scenario_comparison.png)
<sub>Figure 1. Annual modeled prevented depression cases. Blue bars are alternative investment scenarios; the green bar is the existing-greenness accounting counterfactual. All bars use the same central health-effect and societal-cost assumptions. The green bar is not a project option or a forecast of vegetation removal.</sub>

**Table 1. Scenario comparison with common population and economic anchors.**

| Scenario | Spatial rule | Cases / yr | Cases / 1,000 adults | Share of adult depression pool | Avoided cost / yr | Cost / resident / yr | Share of city GDP |
|---|---|---:|---:|---:|---:|---:|---:|
| Uniform +0.05 NDVI (reference) | Raise every valid pixel by 0.05 NDVI; reference only, not physically feasible everywhere. | 4,867 | 6.8 | 3.3% | $103,573,428 | $125 | 0.041% |
| Greenable-only +0.05 NDVI | Raise pixels below NDVI 0.60 by 0.05; data-light feasibility screen. | 4,700 | 6.6 | 3.2% | $100,026,235 | $120 | 0.040% |
| LULC-masked feasible greening | Raise eligible NLCD developed-open, low-intensity, and barren land toward NDVI 0.65. | 596 | 0.8 | 0.4% | $12,681,043 | $15 | 0.005% |
| 30% canopy target | Raise each tract toward the NDVI equivalent of 30% tree canopy; policy target. | 35,317 | 49.3 | 24.2% | $751,537,448 | $905 | 0.301% |
| Within-city p95 potential | Raise lower-NDVI pixels to the city's own 95th-percentile NDVI; ambitious upper-bound potential. | 39,013 | 54.4 | 26.7% | $830,202,625 | $1,000 | 0.332% |
| Health-priority feasible allocation | Allocate the same feasible-NDVI budget first to tracts with highest modeled cases per feasible NDVI increment. | 476 | 0.7 | 0.3% | $10,135,939 | $12 | 0.004% |
| Equity-priority feasible allocation | Allocate the same feasible-NDVI budget using health need, SVI, and low-greenness priority. | 309 | 0.4 | 0.2% | $6,584,181 | $8 | 0.003% |
| Balanced feasible allocation | Allocate the same feasible-NDVI budget using equal health and equity priority weights. | 322 | 0.4 | 0.2% | $6,860,278 | $8 | 0.003% |
| Existing greenness (accounting counterfactual) | Current NDVI compared with NDVI = 0; upper-bound stock value, not an investment scenario. | 21,321 | 29.7 | 14.6% | $453,715,456 | $546 | 0.181% |

<sub>Table 1 legend. All values are annual central estimates, not confidence intervals. Cases per 1,000 adults use 716,727 adults. The adult depression pool is 146,212 (20.4% prevalence). Cost per resident uses 830,235 residents; GDP shares use $250B. Costs use the configured $21,280 per case. The existing-greenness row is an upper-bound accounting comparison, not an investment scenario.</sub>

The LULC-masked and canopy-target scenarios are the most decision-relevant; the uniform and p95 scenarios bracket a simple reference and an ambitious upper bound.

## Where the benefits concentrate

Benefits are largest where many people live near low greenery and depression rates are high. The map shows avoided cost by neighborhood; the scatter shows that higher-prevalence neighborhoods gain more from greening.

![Avoided societal cost per neighborhood, from added greenery.](../figures/map_marginal_cost.png)
<sub>Avoided societal cost per neighborhood, from added greenery.</sub>

## Equity implications

We assess the distribution of the modeled *rate* of prevented cases using two complementary rankings: median household income and CDC/ATSDR Social Vulnerability Index (SVI). This is a distributional diagnostic, not evidence that a real project will reach vulnerable residents without deliberate siting and implementation.

| Equity lens | Concentration index | Interpretation |
|---|---:|---|
| Median household income (low → high) | +0.020 | no material gradient detected |
| CDC/ATSDR SVI (low → high vulnerability) | -0.028 | benefits concentrate in less socially vulnerable neighborhoods (equity concern) |

For income, a negative index favors lower-income tracts. For SVI, a positive index favors more socially vulnerable tracts. Values within ±0.02 are treated as no material gradient.

![Income and SVI concentration curves](../figures/equity_concentration_curves.png)
<sub>Each curve is ranked separately; above the diagonal means concentration toward the lower end of that specific rank.</sub>

## Advanced distributional equity

This extension reports **relative inequality** (concentration index, CI) and **absolute inequality** (Slope Index of Inequality, SII) in modeled preventable cases per 1,000 adults. For SVI, positive CI/SII means the modeled benefit is more concentrated in socially vulnerable tracts. Intervals are 95% tract-bootstrap intervals; they quantify geographic sampling variation but do not replace the health-effect sensitivity analysis.

**Table 3. SVI distribution of benefit by scenario.**

| Scenario | SVI CI (95% interval) | SII cases / 1,000 adults (95% interval) | Interpretation |
|---|---:|---:|---|
| Uniform +0.05 NDVI (reference) | -0.022 (-0.031, -0.011) | -0.75 (-1.08, -0.39) | vulnerability-under-serving |
| Greenable-only +0.05 NDVI | -0.012 (-0.022, -0.002) | -0.40 (-0.72, -0.07) | no material gradient |
| LULC-masked feasible greening | -0.090 (-0.226, +0.024) | -0.38 (-0.88, +0.12) | vulnerability-under-serving |
| 30% canopy target | +0.029 (+0.013, +0.046) | +7.31 (+3.39, +11.72) | equity-promoting |
| Within-city p95 potential | +0.020 (+0.005, +0.036) | +5.65 (+1.45, +9.88) | equity-promoting |
| Health-priority feasible allocation | -0.139 (-0.256, -0.029) | -0.47 (-0.86, -0.09) | vulnerability-under-serving |
| Equity-priority feasible allocation | +0.306 (+0.182, +0.399) | +0.67 (+0.33, +1.07) | equity-promoting |
| Balanced feasible allocation | +0.272 (+0.149, +0.382) | +0.62 (+0.28, +1.06) | equity-promoting |

<sub>Table 3 legend. CI is a relative distribution measure; SII is the modeled difference between the least and most socially vulnerable ends of the population-weighted SVI rank. Both use adult-population weights.</sub>

![Figure 3. Relative and absolute SVI inequality across scenarios; error bars show 95% tract-bootstrap intervals.](../figures/equity_svi_inequality_intervals.png)
<sub>Figure 3. Relative and absolute SVI inequality across scenarios; error bars show 95% tract-bootstrap intervals.</sub>

![Figure 4. Health–equity trade-off. Higher vertical position means more modeled benefit reaches higher-SVI tracts.](../figures/equity_health_pareto.png)
<sub>Figure 4. Health–equity trade-off. Higher vertical position means more modeled benefit reaches higher-SVI tracts.</sub>

![Figure 5. Equity-priority score for feasible greening, combining modeled cases per feasible NDVI increment, SVI, and baseline greenness deficit.](../figures/equity_priority_map.png)
<sub>Figure 5. Equity-priority score for feasible greening, combining modeled cases per feasible NDVI increment, SVI, and baseline greenness deficit.</sub>

![Figure 6. Local spatial clusters of the equity-priority score; this is a screening map for place-based planning, not a causal inference map.](../figures/equity_priority_clusters.png)
<sub>Figure 6. Local spatial clusters of the equity-priority score; this is a screening map for place-based planning, not a causal inference map.</sub>

## Interpreting the scale columns

The population, depression-pool, resident-cost, and GDP measures in Table 1 are calculated separately for **every** scenario using the same city-wide denominators. They are included in the table precisely to avoid treating the uniform +0.05 reference scenario as the only result. Compare investment scenarios primarily on their spatial feasibility and these standardized benefit metrics; interpret the existing-greenness row only as the current stock of modeled benefit.


## How reliable are these numbers?

Two sources of spread, and they are different in kind:

- **Statistical 95% CI (cases).** The effect-size bounds (RR 0.908–0.982) are the Liu et al. (2023) odds-ratio 95% CI, converted to risk ratios. Propagating them gives the headline confidence interval of 1,549–8,073 cases.
- **Cost scenario band ($17k–$23k per case).** This is a range of defensible cost-of-illness anchors, *not* a statistical CI — treat it as a what-if range.

The chart and table below show both together.

![How avoided cost changes with the effect size and cost-per-case range.](../figures/sensitivity_range.png)
<sub>How avoided cost changes with the effect size and cost-per-case range.</sub>

| effect size (RR) | cases prevented | cost (low) | cost (central) | cost (high) |
|---|---:|---:|---:|---:|
| 0.908 | 8,073 | $137,234,774 | $171,785,647 | $185,670,577 |
| 0.944 | 4,867 | $82,741,930 | $103,573,428 | $111,944,964 |
| 0.982 | 1,549 | $26,337,096 | $32,967,848 | $35,632,542 |

### Sensitivity to the baseline-risk assumption (p0)

Baseline risk p0 used: **0.204** (population-weighted PLACES prevalence); central OR 0.931 -> RR 0.9443. The RR is nearly flat in p0, but preventable cases scale with -ln(RR), so they move ~±6% per 0.05 change in p0 — hence pinning p0 to the data (compute_p0.py):

| p0 | RR | approx. preventable cases |
|---:|---:|---:|
| 0.10 | 0.9375 | 5,483 |
| 0.15 | 0.9407 | 5,187 |
| 0.20 | 0.9440 | 4,891 |
| 0.25 | 0.9473 | 4,593 |
| 0.30 | 0.9507 | 4,295 |

### Baseline, PAF & population check

- **Population-attributable fraction (PAF): 2.84%** — the share of baseline depression preventable at +0.05 NDVI (RR 0.944). Dimensionless, so it is directly comparable across places regardless of size or age structure.
- Model-implied baseline depression cases: **171,359** (= preventable / PAF).
- Census-based adult depression pool: **146,212** (716,727 adults × 20.4%).
- ⚠️ Model baseline is **1.17×** the census pool → the population raster likely sums ~839,995 (vs 716,727 adults). Check that population was adult-scaled AND clipped to the AOI polygon (not a bounding box). Fixing it scales the headline down by ~15%.

## How this compares with other studies

- **Greening magnitude.** Our +0.05 NDVI scenario is close to the Barcelona "Eixos Verds" green-corridor plan, whose health impact assessment modelled an average **+0.059 NDVI** (Vidal Yáñez et al., 2023) — so the dose is realistic, not arbitrary.
- **Method precedent.** Wu et al. (2025) use the same design — scenario-based preventable depression burden from greenness via a pooled meta-analytic odds ratio and population-attributable fractions — so the approach is established and publishable.
- **Effect magnitude.** Published per-0.1-NDVI depression reductions cluster around **5–8%**; our risk ratio gives **5.6%** per 0.1 NDVI (converted from the Liu et al., 2023 odds ratio) — at the conservative end, as expected after the OR→RR correction (the higher figures use the OR directly).
- **Takeaway.** The preventable *fraction* is defensible and literature-consistent; the absolute count depends on the population baseline (see check above).

_Sources: Liu et al. (2023); Vidal Yáñez et al. (2023); Wu et al. (2025) — see References._

## Data-quality checks

- Cost bookkeeping: implied $21,280/case vs configured $21,280 — OK.
- Population is adult-scaled (depression rates are for adults); the baseline check above confirms it against census figures.
- The greening scenario and effect size are assumptions — read the headline with the ranges above, not as a single certain number.
- **Cross-place comparability:** we report the **PAF** and **cases per 1,000 adults**, which are independent of a place's size and age structure. A full *age-standardized* rate (as in Wu et al., 2026) is **not feasible here**: CDC PLACES gives a single adult (18+) depression rate per tract, not 5-year age-specific rates, and the effect size isn't age-specific — so the PAF and the crude adult rate are the appropriate comparators.

## Glossary

- **NDVI** — a satellite greenery index from 0 to 1; higher = more vegetation. A +0.05 rise is a modest, realistic increase.
- **Prevented (preventable) cases** — depression cases expected *not* to occur when greenery increases, based on published greenery–depression studies.
- **Societal cost** — the full annual cost of a depression case (healthcare plus lost productivity), not just medical bills.
- **Census tract** — a neighborhood-sized area (~4,000 people) used for the maps.
- **Effect size (risk ratio)** — how much depression risk changes per +0.1 NDVI.

## References

Centers for Disease Control and Prevention/Agency for Toxic Substances and Disease Registry/Geospatial Research, Analysis, and Services Program. (2024). *CDC/ATSDR Social Vulnerability Index 2022 Database* [Data set]. https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html

Centers for Disease Control and Prevention. (2024). *PLACES: Local data for better health (census tract and county data)* [Data set]. https://www.cdc.gov/places

Greenberg, P. E., Fournier, A.-A., Sisitsky, T., Simes, M., Berman, R., Koenigsberg, S. H., & Kessler, R. C. (2021). The economic burden of adults with major depressive disorder in the United States (2010 and 2018). *PharmacoEconomics, 39*(6), 653–665. https://doi.org/10.1007/s40273-021-01019-4

Greenberg, P. E., Fournier, A.-A., Sisitsky, T., Simes, M., Berman, R., Koenigsberg, S. H., & Kessler, R. C. (2023). The economic burden of adults with major depressive disorder in the United States (2019). *Advances in Therapy, 40*(9), 4460–4479. https://doi.org/10.1007/s12325-023-02622-x

König, H., König, H.-H., & Konnopka, A. (2020). The excess costs of depression: A systematic review and meta-analysis. *Epidemiology and Psychiatric Sciences, 29*, Article e30. https://doi.org/10.1017/S2045796019000180

Liu, Z., Chen, X., Cui, H., Ma, Y., Gao, N., Li, X., Meng, X., Lin, H., Abudou, H., Guo, L., & Liu, Q. (2023). Green space exposure on depression and anxiety outcomes: A meta-analysis. *Environmental Research, 231*(Pt 3), Article 116303. https://doi.org/10.1016/j.envres.2023.116303

Natural Capital Project. (2024). *InVEST: Integrated Valuation of Ecosystem Services and Tradeoffs (Urban Mental Health model)* [Computer software]. Stanford University. https://naturalcapitalproject.stanford.edu/software/invest

U.S. Bureau of Economic Analysis. (2024). *Gross domestic product by county* [Data set]. https://www.bea.gov/data/gdp/gdp-county-metro-and-other-areas

U.S. Census Bureau. (2024). *Cartographic boundary files (2024 vintage)* [Data set]. https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html

Vidal Yáñez, D., Pereira, E., Cirach, M., Daher, C., Nieuwenhuijsen, M., & Mueller, N. (2023). An urban green space intervention with benefits for mental health: A health impact assessment of the Barcelona "Eixos Verds" Plan. *Environment International, 174*, Article 107880. https://doi.org/10.1016/j.envint.2023.107880

WorldPop. (2025). *Global 2015–2030 constrained population estimates (Global2), Release R2025A* [Data set]. University of Southampton. https://hub.worldpop.org/geodata/listing?id=135

Wu, J., Di, W., Ruan, J., Li, S., Ying, J., Zhou, J., Rudan, I., & Song, P. (2025). The global, regional and national preventable burden of depression attributable to greenness and inequalities: A scenario-based health impact analysis. *Journal of Global Health, 15*, Article 04280. https://doi.org/10.7189/jogh.15.04280

Wu, J., Ruan, J., Di, W., Ying, J., Zhou, J., Luo, Z., Rudan, I., & Song, P. (2026). The global burden of hypertension preventable by urban greenness. *Nature Health.* https://doi.org/10.1038/s44360-026-00090-5

Zhang, J., & Yu, K. F. (1998). What's the relative risk? A method of correcting the odds ratio in cohort studies of common outcomes. *JAMA, 280*(19), 1690–1691. https://doi.org/10.1001/jama.280.19.1690

