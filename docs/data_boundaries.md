# Census boundary files: cartographic (cb_) vs TIGER/Line (tl_)

**Project convention: use the CARTOGRAPHIC (`cb_<year>_us_*_500k`) boundary files
for all analysis** (counties, metros/CBSAs, and any Census boundary layer). This
matches the reference notebook (`00b1-aoi-places-in-metro.ipynb`, which uses
cb_2020) and gives cleaner, shoreline-clipped geometry for coastal metros.

`build_metro_counties.py` defaults to `--cartographic` (use `--no-cartographic`
only if you specifically need full-resolution geometry).

## Key differences

| | `cb_` cartographic (`_500k`) — **use this** | `tl_` TIGER/Line |
|---|---|---|
| Geometry detail | Generalized/simplified (1:500,000) | Full resolution (every vertex) |
| Coastline / water | **Clipped to shoreline** (land only) | Extends to legal limits in bays/ocean |
| File size / speed | Small, fast | Large |
| Attributes | Core (GEOID, NAME, STATEFP, LSAD, …) | Full (adds ALAND, AWATER, INTPTLAT, …) |
| Download path | `…/GENZ<year>/shp/cb_<year>_us_<kind>_500k.zip` | `…/TIGER<year>/<KIND>/tl_<year>_us_<kind>.zip` |
| Best for | Cartography, national overviews, AOI selection | Precise geometry / exact area calcs |

## Why it matters here

- In the **locked national analysis**, county membership does not come from a
  spatial join. It comes from the official CBSA-to-county delineation crosswalk;
  the county geometry is then used for modelling, clipping, and mapping.
- The geometry choice matters for those modelling and mapping steps, especially
  near coasts. `cb_` avoids the water extensions present in `tl_` boundaries.
- The script's optional geometry-reconstruction mode (`--overlap`) is different:
  it computes county–metro intersection areas in EPSG:5070. For that optional
  method, `tl_` is preferable if exact overlap areas are needed; `cb_` areas are
  generalized.

## National metropolitan-county inclusion rule (locked analysis)

The national results use **whole-county membership**, not a county area-overlap
cutoff. `src/national/build_metro_counties.py` defaults to the official [2020
Census/OMB CBSA delineation List 1](https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2020/delineation-files/list1_2020.xls):

1. Retain crosswalk rows designated **Metropolitan Statistical Area**.
2. Join their five-digit state-plus-county FIPS codes to the county geometry.
3. Exclude Alaska, Hawaii, Puerto Rico, Guam, the U.S. Virgin Islands, American
   Samoa, the Northern Mariana Islands, and—by default—the District of Columbia.

There is **no `--min-overlap` threshold** in that locked method: if the official
crosswalk assigns a county to an MSA, the entire county is included; if not, it
is excluded. The resulting locked AOI contains **1,167 counties in 376 MSAs**,
represented in 47 conterminous states. Connecticut is absent because the 2024
county layer uses planning-region county equivalents but the 2020 crosswalk uses
the former county system. This is a coverage limitation, not a failed county
run. `config/regions.csv` is the authoritative GEOID list and
`data/national/counties.gpkg` is its matching geometry.

### Data sources and the Connecticut coverage issue

The AOI used for the reported analysis combines two Census products:

- **Reported version:** [2020 Census/OMB List 1
  (`list1_2020.xls`)](https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2020/delineation-files/list1_2020.xls)
  for CBSA membership, paired with [2024 Census cartographic counties
  (`cb_2024_us_county_500k.zip`)](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip)
  for county geometry.

Connecticut is absent because the 2020 Census/OMB List 1 represents the state
using its former eight counties, whereas the 2024 Census cartographic county
layer represents it using nine planning-region county equivalents. The two
systems have different GEOIDs and therefore cannot be joined. Rhode Island
retained its county system and does not have this mismatch.

The reported pairing arose from the AOI builder's practical default to use the
then-current generalized Census cartographic county layer. It was not an
intentional cross-vintage harmonization strategy. It is retained here to
preserve reproducibility of the reported results.

## Candidate harmonized 2023 national AOI (not yet promoted)

`provenance/aoi_2023/` records a separate, validated modernization candidate.
It pairs the July 2023 official CBSA List 1 membership crosswalk with
full-resolution 2023 TIGER/Line county-equivalent geometry. The candidate has
1,180 Metropolitan Statistical Area counties in its declared CONUS-plus-DC
scope, compared with 1,167 in the locked AOI. It retains the entire county when
the crosswalk lists it as an MSA member; it does not use the optional geometry
overlap threshold. The locked AOI remains the source for all reported results
unless and until this candidate is explicitly promoted and the national pipeline
is rerun.

The candidate uses the following paired sources:

- **Harmonized version:** [July 2023 Census/OMB List 1
  (`list1_2023.xlsx`)](https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx)
  for CBSA membership, paired with [2023 full-resolution TIGER/Line counties
  (`tl_2023_us_county.zip`)](https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip)
  for county geometry.

Both sources use the current Connecticut planning-region county equivalents,
so the GEOIDs join and Connecticut planning regions that are official MSA
members are included. Before promoting this AOI, the project should confirm
whether other ecosystem-service analyses use the reported AOI and whether all
services should be updated consistently.

### Alternative geometry-based reconstruction (not used for the locked run)

`--overlap --metro-layer <layer> --min-overlap 0.30` is an optional way to
rebuild an AOI from a custom metro polygon layer. It retains a county only when
the sum of its intersections with Metro polygons is at least 30% of that
county's EPSG:5070 area; a county merely touching a Metro polygon is excluded.
This 30% cutoff is therefore an **alternative sensitivity/reconstruction rule**,
not the inclusion criterion for the reported 1,167-county results. A custom
`--metro-layer` affects selection only when paired with `--overlap`.

## Vintage

`cb_` files are published per year under `GENZ<year>/`. Default here is the
`--year` value (2024). Use `--year 2020` to match the notebook's cb_2020 vintage,
or pass your own metro layer via `--metro-layer` for an exact match.

Source: US Census Cartographic Boundary Files —
https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html

## SF AOI provenance + water tracts (verified 2026-07)

The live SF `aoi.gpkg` was built from the **cartographic `cb_2024_06_tract_500k`**
tracts (the `build_aoi_prevalence.py --source api` path): **244 tracts, 2020
vintage, EPSG:26910**. The *local* shapefile
`raw/cdc_places/prevalence_rate_usa_2021.shp` is the older **TIGER/Line (`tl_`),
2010 vintage (196 SF tracts)** and reaches −123.01° longitude (Farallon Islands,
~27 mi offshore); we do **not** use it for the AOI.

Even the cartographic county tract set for SF (`COUNTYFP 075`) legally includes
**3 water / uninhabited tracts** — `06075980401` (Farallon Islands),
`06075990100`, `06075990200` (bay/ocean) — which have null depression prevalence
and zero population. They don't affect case/cost totals but blow up the AOI
extent (~79 km E-W) and clutter maps. `build_aoi_prevalence.py` now drops them by
default (`--drop-nodata`; `--no-drop-nodata` to keep every legal tract), giving a
clean ~city land footprint.

Takeaway: `cb_` (cartographic, shoreline-clipped, current vintage) is the correct
choice for representing the city and for publication maps; `tl_` is larger and,
here, also older. This confirms the project-wide cartographic convention above.
