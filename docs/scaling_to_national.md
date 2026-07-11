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

1. **Define the urban AOIs.** Replace the single SF box/tracts with a national
   set of cities — e.g. Census **Urban Areas (2020)**, **Places**, or **CBSAs**.
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
- **Effect size.** The 0.93 default is national; sensitivity runs (0.887–0.977)
  matter more when totals are large.
- **Suppressed prevalence.** CDC PLACES suppresses small/low-population tracts;
  decide how to handle gaps (drop, impute, or county fallback).

## Suggested engineering shape

```
config/cities.csv                # list of AOIs (GEOID_PLAC, name) to process
src/run_city.py                  # build inputs + run model for ONE city id
run_national.sh                  # loop config/cities.csv -> src/run_city.py
data/urban-mental-health/
  └── workspace/<GEOID_PLAC>/    # per-city outputs, aggregated at the end
```

Parameterize the existing scripts by `--aoi`/`--geoid`/`--crs` (most already
accept paths), drive them from a cities list, and parallelize across cities
(they're independent). Cache the shared national rasters (WorldPop, NDVI tiles)
so each city reads a window rather than re-downloading.

## Bottom line

Scaling is mostly (a) swapping the SF AOI for a national city list, (b) moving to
`EPSG:5070`, and (c) wrapping the per-city steps in a loop with per-city
workspaces — not new science. The prevalence, population, cost, and effect-size
inputs are already national. I can scaffold `run_city.py` + `run_national.sh`
and a `config/cities.csv` when you're ready.
