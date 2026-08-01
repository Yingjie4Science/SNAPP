# Mental-health benefits of existing urban greenness as a Gross Ecosystem Product component

**Service:** Mental health benefits of urban green space

**Scenario:** `existing_greenness` only

**Geographic unit:** U.S. metropolitan-area counties in the locked national study domain

**Accounting period and currency:** Annual service flow, valued in 2024 U.S. dollars

**Lead/POC:** Yingjie Li, [yingjieli@stanford.edu](mailto:yingjieli@stanford.edu), Natural Capital Alliance, Woods Institute for the Environment, Doerr School of Sustainability, Stanford University, Stanford, CA 94305, USA

**Technical-note version:** 1 August 2026

## Executive summary

This analysis estimates one contribution of urban ecosystems to Gross Ecosystem
Product (GEP): the annual mental-health benefit associated with residential
exposure to existing greenness. GEP is the aggregate monetary value of final
ecosystem-related goods and services in a defined area and accounting period
(Ouyang et al., 2020; Zheng et al., 2023). The present result is therefore a
**single GEP service component**.

The `existing_greenness` scenario compares observed 2024 greenness with an
NDVI = 0 reference. It asks:

> What annual burden of PLACES-defined diagnosed depressive disorder is
> associated, under the model, with the greenness that metropolitan counties
> already contain, relative to a zero-NDVI accounting reference?

Across the locked study domain of **1,167 counties**, representing
**218,643,229 adults**, the central model estimates **12,733,902 cases per year**
(**58.24 per 1,000 adults**, or **5.824% of the adult population**) and
**$270.98 billion per year** in associated societal cost. All expected counties
passed completeness, population-reconciliation, and finite-output checks.

These values are modeled prevalence-based counterfactuals. They are **not
observed case reductions, incidence estimates, causal effects, randomized
intervention forecasts, asset values, or net present values**. The NDVI = 0
reference is outside the exposure range of real metropolitan counties and
should be labeled an **upper-bound accounting comparison**. It should not be
described as the predicted consequence of removing all vegetation.

## 1. GEP accounting boundary

### 1.1 Ecosystem service and beneficiary

- **Ecosystem contribution:** vegetated land cover expressed through remotely
  sensed residential greenness (NDVI).
- **Final benefit:** a modeled reduction in the prevalent burden of depressive
  disorder associated with nearby greenness.
- **Beneficiaries:** adults living in the modeled metropolitan counties.
- **Health quantity:** modeled annual cases associated with existing greenness.
- **Monetary quantity:** modeled cases multiplied by the annual incremental
  societal cost per prevalent case.

The result is a service flow for **one year**. It is not the value of the
underlying ecosystem asset or the capitalized value of future service flows.

### 1.2 Valuation interpretation

The monetary estimate uses an avoided-cost/cost-of-illness approach. It values
the modeled health benefit using costs that society bears when depression is
present, including direct healthcare and indirect productivity, household, and
suicide-related burdens. It is not a willingness-to-pay or welfare-surplus
measure. Consequently, it should be reported as:

> **Modeled annual societal cost associated with depressive-disorder cases
> linked to existing greenness under an NDVI = 0 accounting reference.**

When this component is combined with other GEP services, analysts should avoid
adding another depression-treatment or productivity-loss estimate for the same
beneficiaries and period. Recreation, amenity, and health valuations should
also be checked for overlapping pathways before aggregation.

## 2. Study domain

The focus study universe contains **1,167 whole counties assigned to U.S.
Metropolitan Statistical Areas** using the official CBSA-to-county delineation
crosswalk and Census cartographic county geometries. It is not a population-
ranked subset containing only the largest metros, despite the shorthand phrase
“major metro counties.” The model runs separately for every county and then
aggregates counties to metropolitan areas where needed.

The current domain covers metropolitan counties in 47 conterminous states.
Alaska, Hawaii, territories, and the District of Columbia are outside the
locked run. Connecticut is also absent because the county layer uses the newer
planning-region county equivalents while the membership crosswalk used the
former county system. This is a **coverage limitation**, not a failed result
among the 1,167 expected counties. 

## 3. Inputs

| Input | Implemented source and vintage | Spatial form | Role in the model |
|---|---|---|---|
| Existing greenness | 2024 Landsat Collection 2, Tier 1, Level 2 surface reflectance through Google Earth Engine; June–September 90th-percentile NDVI | 30 m county exports, harmonized to aligned 90 m EPSG:5070 grids | Observed residential greenness in the alternate state |
| Depression prevalence | CDC PLACES 2023 tract release, measure `DEPRESSION`, based on 2021 BRFSS; Florida nulls bridged only from the official preceding PLACES 2022 release | Census-tract polygons, rasterized as `risk_rate` | Baseline adult prevalence surface |
| County and tract geometry | U.S. Census cartographic boundary products and locked county GEOIDs | Vector polygons | Study domain, prevalence geography, and reporting units |
| Population distribution | WorldPop Global 2015–2030, R2025A, constrained 2024 population | 100 m people-per-pixel raster | Within-county allocation of residents |
| Adult population totals | ACS 2023 five-year estimates, adult population from table B09021 and total population from B01003 | County table | Exact age-18+ calibration targets |
| Exposure-response | Liu et al. (2023) pooled OR per +0.1 NDVI, converted to a risk ratio | Aspatial parameter | Converts greenness difference to relative risk |
| Societal cost | Pooled recent U.S. Major Depressive Disorder (MDD) cost-of-illness studies, inflation-adjusted | Aspatial national parameter | Converts modeled cases to 2024 USD |

### 3.1 Difference to the physical health modeling

The finalized national run does **not** use the Copernicus 300 m
NDVI product or a 2024 annual-average composite. It uses a cloud- and
saturation-masked **2024 June–September Landsat p90 NDVI composite**, followed
by area averaging and grid harmonization to 90 m. The p90 composite represents
peak growing-season greenness rather than year-round mean greenness.

The primary valuation does **not** use Census-region MEPS treatment cost.
MEPS is retained as a **direct-medical comparator**, while the main result applies
a national **$21,280 societal cost per case**. Regional wage adjustment is a
supplementary distributional sensitivity and was not used here.

## 4. Methods

### 4.1 Spatial harmonization and population calibration

All national calculations use NAD83 / Conus Albers (EPSG:5070). Original
Landsat county exports at 30 m were area-averaged to a common, aligned 90 m
grid. A full-pixel audit required every expected GeoTIFF to be readable, to
contain finite valid values in the NDVI range [-1, 1], and to use consistent
nodata encoding.

WorldPop supplies the relative distribution of people within each county. Its
people-per-pixel counts are mass-conserved during reprojection and then scaled
to the exact ACS 2023 five-year age-18+ total for that county. This retains the
WorldPop spatial pattern while ensuring that county case totals use an adult
population denominator consistent with PLACES.

### 4.2 Residential greenness exposure

For every populated model pixel $j$, InVEST calculates mean NDVI within a
**300 m residential search radius**. Let $G_{0j}$ and $G_{1j}$ be the
neighborhood-average NDVI in the reference and observed states, respectively.
The exposure contrast is

\[
\Delta G_j = G_{1j} - G_{0j}.
\]

For `existing_greenness`, the model inputs are:

\[
G_{0j}=0, \qquad G_{1j}=G_{\mathrm{observed},j}.
\]

Thus, the alternate state is current 2024 greenness and the reference is a
synthetic zero-NDVI surface. This direction is important: the result measures
the modeled benefit of the current state relative to the accounting reference.

### 4.3 Baseline prevalence and baseline cases

CDC PLACES provides the tract-level percentage of adults who report ever being
told by a health professional that they had a depressive disorder. The measure
is converted to a proportion $p_j$ and rasterized to the population grid.
It is broader than current major depressive disorder and should be named
**PLACES-defined diagnosed depressive disorder** on first use.

Baseline prevalent cases in pixel $j$ are

\[
B_j=P_jp_j,
\]

where $P_j$ is calibrated adult population. The completed run supplied
**59,162 valid PLACES tract features**. The separate reference-risk calculation
used 59,161 eligible tracts after its additional population-and-NDVI eligibility
filter.

Florida requires one documented exception: all depression values in the PLACES
2023 release were null because Florida did not meet 2021 BRFSS collection
requirements. The pipeline fills those nulls only with matching official
PLACES 2022 values on the same tract geography; no non-null value or other state
is replaced.

### 4.4 Exposure-response estimate and OR-to-RR conversion

Liu et al. (2023) report a pooled odds ratio

\[
OR_{0.1}=0.931 \quad (95\%\ CI: 0.887\text{–}0.977)
\]

per +0.1 NDVI for depression. Because InVEST requires a risk ratio and the
outcome is common, the odds ratio is converted using the Zhang–Yu approximation:

\[
RR_{0.1}=\frac{OR_{0.1}}{(1-p_0)+p_0OR_{0.1}}.
\]

The locked reference risk is the adult-population-weighted PLACES prevalence
among tracts in the lowest population-weighted national NDVI quartile:

\[
p_0=0.191045.
\]

The quartile threshold is mean NDVI = 0.416390 and contains 14,993 reference
tracts. The resulting central risk ratio is

\[
RR_{0.1}=0.943436
\]

with converted OR confidence limits 0.906571–0.981312. The model does not pass
the published odds ratio directly as if it were a risk ratio.

### 4.5 Modeled cases associated with existing greenness

For pixel $j$, InVEST scales the per-0.1-NDVI risk ratio to the observed
exposure contrast:

\[
RR_j=\exp\left[\ln(RR_{0.1})\,10\Delta G_j\right]
    =RR_{0.1}^{10\Delta G_j}.
\]

The modeled preventable fraction and cases are

\[
PF_j=1-RR_j,
\]

\[
q_j=PF_jB_j
    =\left(1-RR_{0.1}^{10\Delta G_j}\right)P_jp_j.
\]

Here $q_j$ is the model quantity associated with existing greenness relative
to the zero-NDVI reference. County $k$ totals are

\[
Q_k=\sum_{j\in k}q_j,
\]

and the population-standardized result is

\[
R_k=1000\frac{Q_k}{\sum_{j\in k}P_j}.
\]

### 4.6 Monetary valuation for GEP

The central annual societal cost per prevalent case is

\[
c=\$21{,}280\quad\text{(2024 USD per case-year)}.
\]

It is the rounded pooled mean of two recent, methodologically comparable U.S.
cost-of-illness estimates (Greenberg et al., 2021, 2023), inflation-adjusted to
2024 USD. It includes direct and indirect burden and is not treatment cost alone.

Pixel and county GEP contributions are

\[
v_j=cq_j,
\]

\[
V_k=\sum_{j\in k}v_j=cQ_k.
\]

Because the same value per case is used in every county, ranking counties by
monetary value produces the same order as ranking them by cases. The project
retains **$17,000–$23,000 per case** as an economic sensitivity range. Applied
to the central modeled case quantity, this gives **$216.48–$292.88 billion per
year**; this interval varies only the economic unit value and is not a full
uncertainty interval.

### 4.7 Aggregation and quality assurance

The model produces per-pixel case and cost rasters and a summary vector/table
for each county. County values are summed to national and metropolitan totals.
A passing national result requires:

1. exactly 1,167 unique expected county GEOIDs;
2. no missing expected county;
3. finite case, cost, population, and rate values;
4. non-negative county case totals and positive population; and
5. adult population within one person of the ACS 2023 target in every county.

The `existing_greenness` row passes all five tests: 1,167 counties, zero
missing, zero bad numeric outputs, and maximum adult-population error of zero
people in the committed summary.

## 5. Key results

### 5.1 National study-domain total

| Metric | Central result |
|---|---:|
| Counties | 1,167 |
| Valid PLACES tract features supplied to county models | 59,162 |
| Adult population | 218,643,229 |
| Modeled cases associated with existing greenness | 12,733,902/year |
| Modeled cases per 1,000 adults | 58.24 |
| Modeled cases as a percentage of adults | 5.824% |
| GEP mental-health component | $270,977,433,363/year |
| Central societal value | $21,280/case-year (2024 USD) |
| Cost-only sensitivity | $216.48–$292.88 billion/year |

Across counties, the unweighted median result is **5,468 cases per year** and
**75.07 cases per 1,000 adults**. County rates range from **16.10 to 118.38 per
1,000 adults**. These unweighted county statistics should not be interpreted as
the experience of the average adult; the population-weighted study-domain rate
is 58.24 per 1,000.

### 5.2 Highest county totals

| Rank | County | GEOID | Adult population | PLACES tracts | Modeled cases/year | Cases/1,000 adults | GEP value/year |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Harris County, Texas | 48201 | 3,515,154 | 785 | 190,393 | 54.16 | $4.052B |
| 2 | Los Angeles County, California | 06037 | 7,790,870 | 2,323 | 183,895 | 23.60 | $3.913B |
| 3 | Cook County, Illinois | 17031 | 4,074,847 | 1,314 | 159,743 | 39.20 | $3.399B |
| 4 | King County, Washington | 53033 | 1,815,592 | 397 | 122,482 | 67.46 | $2.606B |
| 5 | Dallas County, Texas | 48113 | 1,941,989 | 527 | 102,837 | 52.95 | $2.188B |
| 6 | Bexar County, Texas | 48029 | 1,529,319 | 362 | 92,260 | 60.33 | $1.963B |
| 7 | Tarrant County, Texas | 48439 | 1,587,266 | 356 | 88,413 | 55.70 | $1.881B |
| 8 | Wayne County, Michigan | 26163 | 1,352,595 | 601 | 87,151 | 64.43 | $1.855B |
| 9 | Middlesex County, Massachusetts | 25017 | 1,304,428 | 317 | 83,148 | 63.74 | $1.769B |
| 10 | Maricopa County, Arizona | 04013 | 3,466,307 | 909 | 79,965 | 23.07 | $1.702B |

The ten highest-total counties account for **9.35%** of the national study-
domain result. Harris County, not Los Angeles County, ranks first in the final
`existing_greenness` output. Los Angeles has the largest modeled adult
population but a lower modeled rate per 1,000 adults than Harris.

### 5.3 Highest metropolitan totals

| Rank | Metropolitan Statistical Area | Counties | Modeled cases/year | GEP value/year |
|---:|---|---:|---:|---:|
| 1 | New York–Newark–Jersey City, NY–NJ–PA | 23 | 679,515 | $14.460B |
| 2 | Chicago–Naperville–Elgin, IL–IN–WI | 14 | 361,897 | $7.701B |
| 3 | Dallas–Fort Worth–Arlington, TX | 11 | 322,411 | $6.861B |
| 4 | Houston–The Woodlands–Sugar Land, TX | 9 | 307,250 | $6.538B |
| 5 | Atlanta–Sandy Springs–Alpharetta, GA | 29 | 299,570 | $6.375B |

The New York metropolitan total excludes Connecticut counties under the
current locked AOI, so it is not a complete value for the modern tri-state
metropolitan footprint.

## 6. Interpretation and limitations

1. **Accounting reference, not intervention.** NDVI = 0 is a synthetic
   reference, not a realistic vegetation-removal scenario. The result should be
   secondary to policy-relevant marginal greening scenarios when discussing
   interventions.
2. **Association, not established causation.** The exposure-response parameter
   comes from observational evidence. Liu et al. report high heterogeneity
   (I² = 94.4%), and the pooled estimate should not be treated as a universal
   causal constant.
3. **Endpoint mismatch.** PLACES measures self-reported lifetime professional
   diagnosis of a depressive disorder, whereas the cost literature concerns
   MDD. This endpoint-to-valuation transfer is a material limitation.
4. **Extrapolation.** The full observed-NDVI contrast is larger than the
   marginal changes on which most epidemiological estimates are based. The
   nonlinear exposure-response is therefore extrapolated over a broad range.
5. **Temporal alignment.** Inputs combine 2024 greenness and WorldPop with
   PLACES estimates based mainly on 2021 BRFSS and ACS 2023 five-year adult
   totals. The result is a harmonized accounting estimate, not a single-year
   contemporaneous observation.
6. **Spatial representation.** A common 90 m grid ensures comparability but
   cannot recover detail absent from any source exported at coarser resolution.
   A 300 m neighborhood mean is a proxy for residential exposure, not a measure
   of actual access, use, quality, safety, or duration of contact with nature.
7. **Population allocation.** WorldPop is used for within-county allocation,
   while a county-wide scalar enforces the ACS adult total. Within-county age
   structure is not modeled explicitly.
8. **Uniform national unit value.** The $21,280 value does not reflect local
   wages, prices, healthcare use, or demographic differences. Regional wage-
   adjusted results belong in a sensitivity analysis rather than the primary
   accounting result.
9. **Coverage.** Connecticut, the District of Columbia, Alaska, Hawaii, and
   territories are not represented. County selection should be updated before
   describing this as complete coverage of all U.S. metropolitan counties.
10. **Potential double counting.** The societal cost already contains multiple
    direct and indirect components. GEP aggregation must not count the same
    health or productivity benefit again under another service heading.

## 7. Outputs and reproducibility

### Curated summaries in this repository

- County results: [`../results/summaries/national_summary_existing_greenness.csv`](../results/summaries/national_summary_existing_greenness.csv)
- Human-readable summary: [`../results/summaries/national_summary_existing_greenness.md`](../results/summaries/national_summary_existing_greenness.md)
- Cross-scenario context: [`../results/summaries/national_scenario_comparison.csv`](../results/summaries/national_scenario_comparison.csv)
- Final QA: [`../results/summaries/national_final_qa.md`](../results/summaries/national_final_qa.md)
- Locked reference-risk calculation: [`../results/summaries/national_p0.md`](../results/summaries/national_p0.md)
- NDVI audit: [`../results/summaries/national_ndvi_audit.md`](../results/summaries/national_ndvi_audit.md)
- Existing county case map: [`../results/figures/national_preventable_cases_map_existing_greenness.png`](../results/figures/national_preventable_cases_map_existing_greenness.png)

### Full raster and vector products in the local data archive

The current archive root is
`/Users/yingjiel/Documents/snapp/SNAPP/data/urban-mental-health/runs/national`.
Under `_mosaics/existing_greenness/` it contains:

- `national_existing_greenness_cases_90m.tif` — modeled cases by pixel;
- `national_existing_greenness_cost_90m.tif` — 2024 USD by pixel;
- corresponding 100 m display/analysis products;
- `national_existing_greenness_tracts.gpkg` — national tract mosaic; and
- `national_existing_greenness_totals.csv` — per-county and national totals.

Each county workspace is under `existing_greenness/<GEOID>/`. Its `output/`
folder contains `preventable_cases_<GEOID>.tif`,
`preventable_cost_<GEOID>.tif`, and
`preventable_cases_cost_sum_<GEOID>.{csv,gpkg}`.

The exact software environment is archived under `environment-locks/`, and
SHA-256 hashes for active raw and configured inputs are recorded in
`reproducibility/input_checksums.csv`. Automated tests verify the committed
county count, exact ACS population reconciliation, finite/non-negative results,
valuation identity, and final QA status.

## 8. Reporting summary 

**Methods:**

> We estimated the annual mental-health contribution of existing urban
> greenness to Gross Ecosystem Product across 1,167 metropolitan-area counties.
> For each populated grid cell, the InVEST Urban Mental Health model calculated
> mean 2024 Landsat NDVI within 300 m and compared observed greenness with a
> synthetic NDVI = 0 accounting reference. CDC PLACES tract prevalence and
> WorldPop population calibrated to ACS 2023 adult totals defined baseline
> prevalent cases. We converted the Liu et al. (2023) pooled odds ratio per 0.1
> NDVI to a risk ratio at the national least-green-quartile baseline risk and
> valued modeled cases at $21,280 per case-year in 2024 U.S. dollars.

**Results:**

> Existing greenness was associated in the model with 12.73 million cases per
> year relative to the zero-NDVI accounting reference,
> equivalent to 58.24 cases per 1,000 adults and $270.98 billion per year in
> societal cost. This upper-bound accounting comparison represents one GEP
> service component and should not be interpreted as a causal prediction of
> vegetation removal or as total metropolitan GEP.

**Figures:**

> **Figure 1. Modeled annual mental-health contribution of existing greenness
> to Gross Ecosystem Product in U.S. metropolitan-area counties (2024 USD).**
> County values equal modeled PLACES-defined diagnosed depressive-disorder cases
> associated with observed 2024 residential greenness relative to an NDVI = 0
> accounting reference, multiplied by $21,280 per case-year. Values are
> prevalence-based modeled associations, not observed or causal case reductions.
> Connecticut, the District of Columbia, Alaska, Hawaii, and territories are not
> included in the locked study domain.

## References

Centers for Disease Control and Prevention. (2026). *PLACES methodology*.
https://www.cdc.gov/places/methodology/index.html

Centers for Disease Control and Prevention. (2026). *PLACES current release
notes*. https://www.cdc.gov/places/current-release-notes/index.html

Greenberg, P. E., Fournier, A.-A., Sisitsky, T., Simes, M., Berman, R.,
Koenigsberg, S. H., & Kessler, R. C. (2021). The economic burden of adults with
major depressive disorder in the United States (2010 and 2018).
*PharmacoEconomics, 39*(6), 653–665.
https://doi.org/10.1007/s40273-021-01019-4

Greenberg, P. E., Fournier, A.-A., Sisitsky, T., Simes, M., Berman, R.,
Koenigsberg, S. H., & Kessler, R. C. (2023). The economic burden of adults with
major depressive disorder in the United States (2019). *Advances in Therapy,
40*(9), 4460–4479. https://doi.org/10.1007/s12325-023-02622-x

Liu, Z., Chen, X., Cui, H., et al. (2023). Green space exposure on depression
and anxiety outcomes: A meta-analysis. *Environmental Research, 231*, 116303.
https://doi.org/10.1016/j.envres.2023.116303

Natural Capital Alliance. (2026). *InVEST Urban Mental Health model API*.
https://invest.readthedocs.io/en/main/api/natcap.invest.urban_mental_health.urban_mental_health.html

Ouyang, Z., Song, C., Zheng, H., et al. (2020). Using gross ecosystem product
(GEP) to value nature in decision making. *Proceedings of the National Academy
of Sciences, 117*(25), 14593–14601. https://doi.org/10.1073/pnas.1911439117

Zheng, H., Wu, T., Ouyang, Z., et al. (2023). Gross ecosystem product (GEP):
Quantifying nature for environmental and economic policy innovation. *Ambio,
52*, 1952–1967. https://doi.org/10.1007/s13280-023-01948-8

U.S. Census Bureau. (2023). *American Community Survey 2019–2023 five-year
estimates*. https://www.census.gov/programs-surveys/acs

U.S. Census Bureau. (2024). *Cartographic boundary files*.
https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html

U.S. Geological Survey. (2024). *Landsat Collection 2 Level-2 surface
reflectance*, accessed through Google Earth Engine.
https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2

WorldPop. (2025). *Global 2015–2030 population, Global2 release R2025A*.
https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/

Zhang, J., & Yu, K. F. (1998). What's the relative risk? A method of correcting
the odds ratio in cohort studies of common outcomes. *JAMA, 280*(19),
1690–1691. https://doi.org/10.1001/jama.280.19.1690
