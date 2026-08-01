# SF NDVI buffer coverage audit

The InVEST model averages NDVI within 300 m of populated cells. The
baseline NDVI raster does not extend across the entire northern/eastern model
buffer, so edge cells may use an incomplete neighborhood.

## Result

- Final calibrated adult population: **716,727**
- Adults whose cell center falls outside the NDVI extent:
  **136.9 (0.0191%)**
- Adults whose full 300 m rectangular neighborhood is not contained in
  the NDVI extent: **656.3 (0.0916%)**
- Adults with full extent coverage: **716,070.7 (99.9084%)**

## Decision

Retain this as an explicit residual edge-effect limitation rather than block
manuscript freeze. Fewer than 0.1% of modeled adults lack full 300 m
extent coverage, so a wider NDVI export would improve spatial completeness but
is very unlikely to change the citywide headline materially. Do not describe
the warning as resolved; cite this quantified audit and avoid over-interpreting
the affected northern/eastern edge.
