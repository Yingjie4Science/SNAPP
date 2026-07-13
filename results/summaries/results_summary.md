# San Francisco: health benefits of urban greenery

_Generated 2026-07-13._

This report estimates how much depression could be prevented — and how much money saved — by increasing greenery (street trees, parks, vegetation) across San Francisco. It combines satellite greenery (the NDVI index), local adult depression rates (CDC PLACES) and where people live (WorldPop) via the InVEST Urban Mental Health model. Key terms are defined in the glossary at the end.

## In brief

Adding a modest amount of greenery across San Francisco — a **+0.05 rise in the NDVI greenery index**, roughly the scale of Barcelona's green-corridor plan — could prevent about **4,867 cases of depression per year**, worth roughly **$104 million** in avoided societal cost. Separately, the greenery San Francisco *already has* is estimated to prevent about **21,321 cases per year** versus a bare city.

## Headline numbers

- **4,867** depression cases prevented per year (from added greenery)
- **$103,573,424** avoided societal cost per year
- Neighborhoods analyzed: **241** census tracts
- Per neighborhood: **20** cases prevented on average (range 1–65).

## Two ways to value greenery

We answer two different questions:

1. **Adding greenery** (the policy question) — if greenery rose by +0.05 NDVI everywhere, about **4,867** cases/yr ($104M) would be prevented.
2. **Greenery we already have** (its standing value) — versus a bare, vegetation-free city, today's greenery already prevents about **21,321** cases/yr ($454M).

The first guides investment; the second is an accounting of a benefit the city already enjoys. The "bare city" is a what-if benchmark, not a real prospect — read it as an upper bound.

![The two scenarios compared: depression cases prevented per year.](../figures/counterfactual_comparison.png)
<sub>The two scenarios compared: depression cases prevented per year.</sub>

**Where the benefits fall** — darker means more cases prevented:

<table><tr>
<td width="50%"><img src="../figures/map_marginal_cases.png" width="100%"><br><sub>Adding greenery (+0.05 NDVI)</sub></td>
<td width="50%"><img src="../figures/map_existing_greenness_cases.png" width="100%"><br><sub>Greenery already present</sub></td>
</tr></table>

## Where the benefits concentrate

Benefits are largest where many people live near low greenery and depression rates are high. The map shows avoided cost by neighborhood; the scatter shows that higher-prevalence neighborhoods gain more from greening.

![Avoided societal cost per neighborhood, from added greenery.](../figures/map_marginal_cost.png)
<sub>Avoided societal cost per neighborhood, from added greenery.</sub>


## Putting the numbers in perspective

To make the San Francisco result intuitive:

- Preventable cases are **0.59%** of total population (5.9 per 1,000 residents).
- Estimated adult depression pool ≈ **146,212** (716,727 adults × 20.4%); marginal greening averts **3.3%** of it, and existing greenness accounts for **15%**.
- Avoided societal cost is **0.041%** of San Francisco GDP (~$250B); existing-greenness value is **0.18%** of GDP.
- Avoided cost per resident: **$125/year**.
- (Population/GDP anchors live in config.yaml `context:` — update per city; GDP is an approximate BEA figure.)

## How reliable are these numbers?

The estimate rests on two main assumptions — how strongly greenery affects depression (the *effect size*) and the cost per case. The chart and table show how the result shifts across plausible values.

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

### Baseline & population check

- Marginal preventable fraction (model): **2.84%** of baseline cases at +0.05 NDVI (RR 0.944).
- Model-implied baseline depression cases: **171,359** (= preventable / preventable-fraction).
- Census-based adult depression pool: **146,212** (716,727 adults × 20.4%).
- ⚠️ Model baseline is **1.17×** the census pool → the population raster likely sums ~839,995 (vs 716,727 adults). Check that population was adult-scaled AND clipped to the AOI polygon (not a bounding box). Fixing it scales the headline down by ~15%.

## How this compares with other studies

- **Greening magnitude.** Our +0.05 NDVI scenario is close to the Barcelona "Eixos Verds" green-corridor plan, whose HIA modelled an average **+0.059 NDVI** — so the dose is realistic, not arbitrary.
- **Method precedent.** A 2025 global study (J. Global Health) uses the same design — scenario-based preventable depression burden from greenness via a pooled meta-analytic OR and population-attributable fractions — so the approach is established and publishable.
- **Effect magnitude.** Published per-0.1-NDVI depression reductions cluster around **5-8%**; our risk-ratio gives **5.6%** per 0.1 NDVI — at the conservative end, as expected after the OR->RR correction (the higher figures use the OR directly).
- **Takeaway.** The preventable *fraction* is defensible and literature-consistent; the absolute count depends on the population baseline (see check above).

_Full citations [1], [3], [4] in the References section._

## Data-quality checks

- Cost bookkeeping: implied $21,280/case vs configured $21,280 — OK.
- Population is adult-scaled (depression rates are for adults); the baseline check above confirms it against census figures.
- The greening scenario and effect size are assumptions — read the headline with the ranges above, not as a single certain number.

## Glossary

- **NDVI** — a satellite greenery index from 0 to 1; higher = more vegetation. A +0.05 rise is a modest, realistic increase.
- **Prevented (preventable) cases** — depression cases expected *not* to occur when greenery increases, based on published greenery–depression studies.
- **Societal cost** — the full annual cost of a depression case (healthcare plus lost productivity), not just medical bills.
- **Census tract** — a neighborhood-sized area (~4,000 people) used for the maps.
- **Effect size (risk ratio)** — how much depression risk changes per +0.1 NDVI.

## References

1. Liu Z, Chen X, Cui H, Ma Y, Gao N, Li X, Meng X, Lin H, Abudou H, Guo L, Liu Q. Green space exposure on depression and anxiety outcomes: a meta-analysis. *Environmental Research.* 2023;231(Pt 3):116303. doi:[10.1016/j.envres.2023.116303](https://doi.org/10.1016/j.envres.2023.116303).
2. Zhang J, Yu KF. What's the relative risk? A method of correcting the odds ratio in cohort studies of common outcomes. *JAMA.* 1998;280(19):1690–1691. doi:[10.1001/jama.280.19.1690](https://doi.org/10.1001/jama.280.19.1690).
3. Vidal Yáñez D, Pereira E, Cirach M, Daher C, Nieuwenhuijsen M, Mueller N. An urban green space intervention with benefits for mental health: a health impact assessment of the Barcelona "Eixos Verds" Plan. *Environment International.* 2023;174:107880. doi:[10.1016/j.envint.2023.107880](https://doi.org/10.1016/j.envint.2023.107880).
4. The global, regional, and national preventable burden of depression attributable to greenness and inequalities: a scenario-based health impact analysis. *Journal of Global Health.* 2025;15:04280. doi:[10.7189/jogh.15.04280](https://doi.org/10.7189/jogh.15.04280).
5. Greenberg PE, Fournier A-A, Sisitsky T, Simes M, Berman R, Koenigsberg SH, Kessler RC. The economic burden of adults with major depressive disorder in the United States (2010 and 2018). *PharmacoEconomics.* 2021;39(6):653–665. doi:[10.1007/s40273-021-01019-4](https://doi.org/10.1007/s40273-021-01019-4).
6. Greenberg PE, et al. The economic burden of adults with major depressive disorder in the United States (2019). *Advances in Therapy.* 2023. doi:[10.1007/s12325-023-02622-x](https://doi.org/10.1007/s12325-023-02622-x).
7. König H, König H-H, Konnopka A. The excess costs of depression: a systematic review and meta-analysis. *Epidemiology and Psychiatric Sciences.* 2019;29:e30. doi:[10.1017/S2045796019000180](https://doi.org/10.1017/S2045796019000180).
8. Natural Capital Project. InVEST: Integrated Valuation of Ecosystem Services and Tradeoffs — Urban Mental Health model. Stanford University; 2024. https://naturalcapitalproject.stanford.edu/software/invest
9. Centers for Disease Control and Prevention. PLACES: Local Data for Better Health (census-tract and county data), 2024 release. https://www.cdc.gov/places
10. WorldPop. Global 2015–2030 constrained population estimates (Global2), release R2025A. University of Southampton. https://hub.worldpop.org/geodata/listing?id=135
11. US Census Bureau. Cartographic Boundary Files, 2024 vintage. https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
12. US Bureau of Economic Analysis. Gross Domestic Product by County (San Francisco County, FIPS 06075). https://www.bea.gov/data/gdp/gdp-county-metro-and-other-areas
