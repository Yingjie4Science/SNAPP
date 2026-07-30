# National NDVI export audit

_Generated 2026-07-30._

## Decision

National completeness is defined by matching the exact county GEOID set in the Earth Engine upload—not by the number of files in Drive.

## Result

- Expected AOI counties: **1167**
- Correctly named GeoTIFFs: **1217**
- Expected files present: **1161**
- Missing expected GEOIDs: **6**
- Unexpected GEOIDs outside the AOI: **56**
- Expected rows not passing current QA: **473**
- Expected-raster resolutions: **30 x 30 m: 694, 90 x 90 m: 467**
- Raster-statistics method: **sampled to <=256 x 256 pixels per raster**

- Missing: `21047, 21049, 21067, 21081, 21103, 21113`
- Unexpected: `01041, 01095, 01109, 05011, 05067, 06005, 12045, 12093, 12125, 13007, 13031, 13157, 18071, 18083, 21099, 21147, 21205, 21235, 22119, 23027, 24023, 24041, 29201, 37039, 37083, 37105, 37163, 37171, 37175, 39043, 41007, 42031, 42033, 42061, 42097, 45021, 45069, 47079, 48223, 48273, 48343, 48379, 51001, 51029, 51083, 51091, 51119, 51139, 51147, 51171, 53029, 54001, 54049, 54109, 55099, 55121`

## Interpretation

Unexpected files are not automatically invalid; they may come from an older AOI export. They must be excluded from the current run or the intended study universe must be revised and re-uploaded consistently. Missing expected files block a complete national run.

## To-do

- Re-export every missing expected GEOID.
- Decide whether unexpected GEOIDs belong in the study universe; do not mix AOI vintages.
- Review every expected row whose `qa_status` is not `pass`.
- Run this audit with `--full-read` before locking the national dataset.
