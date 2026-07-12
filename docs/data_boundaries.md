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

- `GEOID`, `NAME`, `STATEFP`, `LSAD` exist in both, so the county↔metro
  `sjoin(intersects)` and the `LSAD == 'M1'` (Metropolitan) filter behave the same.
- **County selection near coasts differs:** `tl_` boundaries reach into water, so
  a metro can "touch" a neighboring coastal county's water extension and pull it
  in. `cb_` (shoreline-clipped) avoids that — a cleaner, more intuitive AOI for
  metros like San Francisco.
- If you ever need **exact overlap areas**, compute them from `tl_` (full-res);
  `cb_` areas are approximate.

## Vintage

`cb_` files are published per year under `GENZ<year>/`. Default here is the
`--year` value (2024). Use `--year 2020` to match the notebook's cb_2020 vintage,
or pass your own metro layer via `--metro-layer` for an exact match.

Source: US Census Cartographic Boundary Files —
https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
