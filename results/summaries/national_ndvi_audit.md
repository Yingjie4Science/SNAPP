# National NDVI export audit

_Generated 2026-07-30._

## Decision

National completeness is defined by matching the exact county GEOID set in the Earth Engine upload—not by the number of files in Drive.

## Result

- Expected AOI counties: **1167**
- Correctly named GeoTIFFs: **1167**
- Expected files present: **1167**
- Missing expected GEOIDs: **0**
- Unexpected GEOIDs outside the AOI: **0**
- Expected rows not passing current QA: **0**
- Required resolution for this audit: **90 m**
- Expected-raster resolutions: **90 x 90 m: 1167**
- Raster-statistics method: **full raster read**

- Missing: `none`
- Unexpected: `none`

## Interpretation

Unexpected files are not automatically invalid; they may come from an older AOI export. They must be excluded from the current run or the intended study universe must be revised and re-uploaded consistently. Missing expected files block a complete national run.

## To-do

- None for this raster gate; the complete harmonized set passes.
