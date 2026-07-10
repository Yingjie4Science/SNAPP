# Alternative NDVI sources (backups)

The active greenness pipeline uses `../ndvi_gee.py` (Landsat via Google Earth
Engine). These are kept as backups / alternatives — they produce the same kind
of `ndvi_base` raster from different sources:

- `download.py` — Copernicus NDVI 300 m via CDSE OData (downloads global 10-daily
  files, clips to SF). Needs CDSE credentials in `.env`.
- `composite_ndvi.py` — composites the Copernicus dekads into one annual-mean
  GeoTIFF (run after `download.py`).
- `ndvi_sentinel2.py` — 10 m Sentinel-2 NDVI via CDSE openEO.

They are not part of `run_pipeline.sh`. Paths were adjusted for this subfolder,
so they still write into `data/urban-mental-health/inputs/` when run directly.
