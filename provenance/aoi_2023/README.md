# Candidate national metropolitan-county AOI: 2023 vintage

This is a **versioned candidate**, not the production AOI. The locked analysis
continues to use `config/regions.csv` and `data/national/counties.gpkg`; neither
file was modified in creating this candidate.

## Definition

The candidate retains each whole county (or county equivalent) listed as a
**Metropolitan Statistical Area** member in the Census/OMB July 2023 List 1
crosswalk. It uses the matching full-resolution 2023 TIGER/Line county geometry.
This avoids the prior mixture of a 2020 membership crosswalk and 2024 geometry,
which omitted Connecticut's planning-region county equivalents.

Declared scope is CONUS plus the District of Columbia. Alaska, Hawaii, and the
territories (STATEFP `02`, `15`, `60`, `66`, `69`, `72`, `78`) remain outside the
current projection and raster workflow; this is a scope restriction, not an
absence of CBSA membership.

## Local source and output artifacts

The large raw and geometry files remain under ignored `data/` paths so this
repository does not duplicate Census distributions. Re-create them exactly with
the command below and verify their SHA-256 hashes.

| Artifact | Local path | SHA-256 |
|---|---|---|
| July 2023 List 1 crosswalk | `data/national/aoi_versions/2023/raw/list1_2023.xlsx` | `952c4b1e78acbb54e6ec9412434b7602fedacbf021736351a63c181bdb753629` |
| 2023 TIGER/Line counties | `data/national/aoi_versions/2023/raw/tl_2023_us_county.zip` | `692e12c30c83adcaabdbac0d3954fafa55e1c89a24b36d95e72e02dff938652e` |
| Candidate AOI GeoPackage | `data/national/aoi_versions/2023/derived/msa_counties_2023.gpkg` | `e7186eaf47e65ba656695c660e6bfb8fb7e6463501b8a535b6a05282b9ca899f` |

Sources: [Census/OMB List 1, July 2023](https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx) and [2023 TIGER/Line counties](https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip).

## Reproduction and validation

Run in the project `snapp` environment:

```bash
python src/national/build_metro_counties.py \
  --year 2023 --no-cartographic \
  --county-layer zip:///absolute/path/to/tl_2023_us_county.zip \
  --crosswalk data/national/aoi_versions/2023/raw/list1_2023.xlsx \
  --keep-dc \
  --out data/national/aoi_versions/2023/derived/msa_counties_2023.gpkg \
  --regions-csv provenance/aoi_2023/regions_cbsa_2023.csv

python src/national/validate_aoi_vintage.py \
  --candidate-gpkg data/national/aoi_versions/2023/derived/msa_counties_2023.gpkg \
  --candidate-regions provenance/aoi_2023/regions_cbsa_2023.csv \
  --crosswalk data/national/aoi_versions/2023/raw/list1_2023.xlsx \
  --include-dc \
  --report provenance/aoi_2023/validation.json \
  --comparison provenance/aoi_2023/compare_legacy_2020_to_cbsa_2023.csv
```

The first command selects membership exclusively from the crosswalk; it does
not use a metro-polygon overlap threshold. The validator must report `passed:
true` before the candidate can be considered for promotion.

## Validation result (2026-11-13)

- Candidate: 1,180 counties across 49 states/territory-equivalents in the
  declared CONUS+DC scope; source crosswalk expectation: 1,180.
- Geometry and regions CSV: no duplicate GEOIDs, no invalid geometries, and no
  discrepancies with each other or the filtered crosswalk.
- Versus the locked 1,167-county AOI: 1,119 shared counties, 61 additions, and
  48 removals. The change is not solely Connecticut; it also reflects updated
  July 2023 CBSA delineations and inclusion of DC. The full county-level diff is
  `compare_legacy_2020_to_cbsa_2023.csv`.

Do not replace production AOI files or rerun national results until the
membership-change table is reviewed and the revised scope is approved.
