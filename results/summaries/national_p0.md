# National lowest-NDVI-quartile baseline risk (p0)

## Locked primary estimate

- **p0: 0.191045**
- Reference group: whole tracts at or below the population-weighted national
  urban NDVI 25% threshold (0.416390 mean NDVI).
- Realized reference population share: 25.001%. Whole-tract
  assignment can differ slightly from exactly 25% at the threshold.
- Converted Liu et al. (2023) RR per +0.1 NDVI:
  **0.943436** (OR-CI conversion: 0.906571–0.981312).

## Data and QA

- AOI counties: 1,167
- Eligible PLACES tracts: 59,161
- Reference-group tracts: 14,993
- ACS adult population represented: 218,643,229
- Adult population with valid NDVI: 218,607,899
  (99.9838%)
- Overall population-weighted PLACES prevalence, shown only as a convergence
  check: 0.211624
- Florida temporal bridge: 4,009
  matched tracts. CDC's 2023 PLACES release has null measures for every Florida
  tract; the immediately preceding 2022 release uses the same outcome and 2015
  tract geography.

## Decision

This is the primary U.S. p0 because the prevalence definition (CDC PLACES),
population universe (adults), geography (the national study AOI), and exposure
distribution (the harmonized baseline NDVI) match the model. Hystad et al.
(2019) lowest-quartile values are retained as outcome-definition sensitivity
anchors, not pooled or averaged into the primary p0.

## Method

Within each county, WorldPop supplies relative spatial weights and the official
ACS 2023 five-year B01001 table supplies the exact age-18+ total. The calibrated
population is aggregated to CDC PLACES tracts on each county's harmonized 90 m
NDVI grid. Tracts are ranked by population-weighted mean NDVI nationally; p0 is
the population-weighted PLACES prevalence among tracts in the lowest weighted
quartile. The resulting p0 and full-precision OR-to-RR conversions are written
to `config.yaml`.
