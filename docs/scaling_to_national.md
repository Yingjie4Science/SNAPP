# Scaling from San Francisco to a US-nationwide urban study

The current pipeline is built for one city, but most of the data sources are
already national. Here's what changes when you scale to all US urban areas.

## What already scales (no new data needed)

- **Depression prevalence** — `raw/cdc_places/prevalence_rate_usa_2021.shp` is the
  *national* CDC PLACES tract file. `build_aoi_prevalence.py` just filters by
  GEOID prefix; drop the SF filter to keep all tracts.
- **Population** — WorldPop US 100 m is national; clip per study area.
- **Health cost** — the societal per-case figure is a US-national value; already
  applies everywhere (see regional refinement below).
- **NDVI (GEE)** — your original Earth Engine script already **loops over many
  city AOIs** (`aoi_cities`, keyed by `GEOID_PLAC`); that pattern is the template.

## What needs to change

1. **Define the AOIs = counties in metros.** `build_metro_counties.py` selects
   US **counties that fall within/overlap a Metro (CBSA)** and writes
   `data/national/counties.gpkg` + `config/regions.csv`. (Project decision: the
   study unit is the county intersecting a metro, not the Census "place" layer.)
   Iterate over them (one AOI per city), as your GEE script does.

2. **Use a national equal-area CRS.** The scripts hardcode `EPSG:26910` (UTM 10N),
   which is correct only for the SF longitude band. For CONUS use
   **`EPSG:5070` (NAD83 / Conus Albers, meters)** everywhere (AOI, population,
   NDVI). Alaska/Hawaii/PR need their own CRS if included.

3. **Loop the model per city, not once nationally.** InVEST buffers the AOI by
   `search_radius` and holds rasters in memory, so run it **per city** (or per
   metro) and aggregate `preventable_cases` / `preventable_cost` afterward. A
   single national raster run is not practical.

4. **Mind GEE compute limits.** National 30 m Landsat is large. Keep per-city
   `Export.image.toDrive` (your script's approach) or batch by state/UTM tile;
   don't try one national `getDownloadURL`.

5. **Memory + I/O.** Reuse the windowed-read pattern from `fetch_population.py`
   (`clip_box` before polygon clip) for every city so you never load the national
   population raster whole.

## Refinements worth adding at national scale

- **Regional cost.** `estimate_health_cost.py` already takes `--region`
  (MEPS census regions) and `--wage-factor`. For a national study, compute a
  cost per case per region (or per metro wage level) rather than one flat value,
  since the workplace component (61%) scales with local wages.
- **Effect size.** National runs read the configured **risk ratio**, not the raw
  Liu odds ratio. The final conversion must use the national low-NDVI-reference
  p0 documented in `docs/effect_size.md`.
- **Suppressed prevalence.** CDC PLACES suppresses small/low-population tracts;
  decide how to handle gaps (drop, impute, or county fallback).

## Suggested engineering shape

```
src/national/build_metro_counties.py   # AOI: counties overlapping metros
config/regions.csv                      # county GEOIDs (written by the builder)
src/national/run_city.py                # build inputs + run model for ONE county
run_national.sh                         # loop config/regions.csv -> run_city.py
data/urban-mental-health/runs/national/<GEOID>/   # per-county outputs
```

Parameterize by `--geoid`/`--regions`/`--crs`, drive from `config/regions.csv`,
and parallelize across counties (they're independent). Cache the shared national
rasters (WorldPop, NDVI tiles) so each county reads a window rather than
re-downloading.

## Required NDVI export gate

Do not use the Drive file count as evidence of completeness. Match files to the
exact county layer uploaded to Earth Engine:

```bash
python src/national/audit_ndvi_exports.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --ndvi-dir data/national/ndvi
```

The audit checks GEOID membership, readability, CRS, resolution, sampled valid
coverage, and NDVI range. Run it again with `--full-read` before locking the
national dataset.

## Required population calibration

WorldPop supplies the within-county spatial pattern, but it is not accepted as
the authoritative aggregate. Build ACS adult targets and let `run_city.py`
rescale each county raster:

```bash
python src/inputs/fetch_adult_fraction.py \
  --regions data/national/counties_gee_upload/counties.shp \
  --out config/adult_population.csv --year 2023
```

This writes `config/adult_population.csv` with county total population, adult
population, and adult fraction. National runs should not proceed with the flat
fallback fraction unless missing-county handling is explicitly justified.

The 2026-07-30 inventory found 1,167 expected counties, 1,161 present, six
missing, and 56 files outside the uploaded AOI. It also found 467 expected
rasters at 90 m rather than the specified 30 m. These are data-preparation
failures to resolve before a national model run, not harmless bookkeeping
differences. The current machine-readable evidence is in
`results/summaries/national_ndvi_manifest.csv`.

## Bottom line

Scaling is mostly (a) locking the county universe, (b) quality-assuring uniform
EPSG:5070 NDVI, and (c) looping per county. The effect-size scaffolding is in
place, but the final national p0 cannot be locked until the NDVI gate passes.
