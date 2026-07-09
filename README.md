# SNAPP

Data and analysis workspace. Code lives under `src/` (one subpackage per
dataset or pipeline); datasets live under `data/`, split into `raw/` (original,
untouched) and `processed/` (analysis-ready, regenerable).

## Project layout

```
SNAPP/
├── README.md
├── .gitignore
├── .env.example              # committed credential template
├── .env                      # real secrets (gitignored)
├── environment.yml           # conda env spec (recommended setup)
├── requirements.txt          # pip alternative
├── run_pipeline.sh           # run all five steps end to end
├── .vscode/                  # shared editor config (interpreter + extensions)
├── src/
│   ├── sf_ndvi/
│   │   ├── download.py       # downloads + clips SF NDVI 2024 (Copernicus 300 m)
│   │   ├── composite_ndvi.py # dekads -> one annual-mean NDVI GeoTIFF (ndvi_base)
│   │   ├── ndvi_sentinel2.py # 10 m NDVI via CDSE openEO (higher-res alternative)
│   │   └── ndvi_gee.py       # 30 m Landsat JJAS p90 NDVI via Google Earth Engine
│   ├── inputs/
│   │   ├── build_aoi_prevalence.py  # SF tracts AOI + CDC PLACES depression (risk_rate)
│   │   ├── fetch_population.py       # WorldPop US 100 m -> clip to SF AOI (local file or download)
│   │   └── make_ndvi_scenario.py    # ndvi_base -> ndvi_alt greening scenario
│   └── urban_mental_health/
│       └── run_model.py      # runs the InVEST Urban Mental Health model
├── data/                     # gitignored — never pushed to GitHub
│   ├── sf-ndvi-2024/
│   │   ├── raw/              # global downloads (temporary)
│   │   └── processed/        # clipped SF outputs
│   ├── urban-mental-health/
│   │   ├── inputs/           # model inputs you supply
│   │   └── workspace/        # model outputs
│   └── meps/
│       ├── raw/              # source MEPS-HC files
│       └── processed/
└── notebooks/                # optional exploratory analysis
```

`data/` is gitignored, so datasets are **not** pushed to GitHub — only code,
config templates, and docs are. Since the data isn't in the repo, each dataset
below documents how to obtain or regenerate it so a fresh clone is reproducible.

## Development setup (VS Code + conda, Apple Silicon)

conda-forge ships arm64 builds of GDAL, `natcap.invest`, `geopandas`, and
`rasterio`, so there's no compiler pain on Apple Silicon (M-series, incl. M5) Macs.

### Where to run these commands

Run them in a terminal **on your Mac**, from the repo root. Easiest is VS Code's
built-in terminal:

1. VS Code → File → Open Folder → select the `SNAPP` folder.
2. Terminal → New Terminal (``Ctrl+` ``). It opens already in the project folder.

Or use the macOS Terminal app and `cd` in first (quotes needed — the path has spaces):

```bash
cd "/Users/<you>/Library/CloudStorage/GoogleDrive-<you>/Shared drives/invest-health/SNAPP"
```

If you get `command not found: conda`, close and reopen the terminal, then retry.
You'll know conda is active when the prompt starts with `(base)`.

### Steps

```bash
# 1. create + activate the environment (from the repo root)
conda env create -f environment.yml
conda activate snapp

# If the env ALREADY exists (e.g. after new packages were added), update instead:
# conda env update -f environment.yml --prune

# 2. sanity check every heavy dep imports (geo + model + openEO + Earth Engine)
python -c "import natcap.invest, geopandas, rioxarray, openeo, ee, geemap; print('env OK')"

# 3. CDSE credentials for the download / Sentinel-2 (openEO) steps
cp .env.example .env      # then edit .env with your CDSE username + password
```

The first solve takes a few minutes (`natcap.invest` + GDAL are large). If
`conda` stalls on "Solving environment", `mamba env create -f environment.yml`
is much faster.

### One-time Earth Engine auth (only for `ndvi_gee.py`)

The GEE route needs a Google account with Earth Engine enabled and a Cloud
project id. The script defaults to project `gee-planet-natcap`; override with
`--project` or `EE_PROJECT` if you use a different one.

```bash
earthengine authenticate               # one-time: opens a browser to sign in
# EE_PROJECT is optional — defaults to gee-planet-natcap
```

In VS Code:
1. Install the recommended extensions (VS Code will prompt from
   `.vscode/extensions.json`, or run "Extensions: Show Recommended Extensions").
2. `Cmd+Shift+P` -> **Python: Select Interpreter** -> choose the `snapp` conda env.
   (`.vscode/settings.json` points at the Miniforge default path; override here if
   your conda lives elsewhere.)
3. Open a new terminal — it should auto-activate `snapp`.

## Datasets

### sf-ndvi-2024 — Copernicus NDVI 300m for San Francisco, 2024

*How to regenerate:* run the downloader (see below). It fetches the Copernicus
**NDVI 300m v2.0** 10-daily global files for 2024 from the Copernicus Data Space
Ecosystem (CDSE) and clips each to a San Francisco bounding box.

- `raw/` — full global NetCDFs as downloaded (deleted after clipping unless
  `KEEP_GLOBAL_FILES = True`).
- `processed/` — one small `.nc` per 10-day dekad, clipped to SF.

The v2.0 product (2020–2025) is *superseded* but still holds 2024 data; a newer
**v3.0** (2014–present) also exists — set `PRODUCT_VERSION = "V3"` in the script
to use it.

### urban-mental-health — InVEST Urban Mental Health model

Runner: `src/urban_mental_health/run_model.py`. Uses the `natcap.invest` Python
API (`urban_mental_health.execute(args)`) to estimate preventable mental-health
cases (and optional societal cost) from residential greenness. NDVI is the
greenness input, so this consumes the `sf-ndvi-2024` dataset.

The model compares a **baseline vs. an alternate (greening) scenario** — either
two NDVI rasters (`model_option='ndvi'`) or two LULC rasters. Inputs go in
`data/urban-mental-health/inputs/`; results land in `.../workspace/`.

Every required input has a script or a sourced value:

| Model input | How it's produced |
|---|---|
| `ndvi_base` | `src/sf_ndvi/ndvi_gee.py` (30 m Landsat JJAS p90) |
| `ndvi_alt` | `src/inputs/make_ndvi_scenario.py` (greening scenario) |
| `aoi_path` + `baseline_prevalence_vector` | `src/inputs/build_aoi_prevalence.py` (SF tracts + CDC PLACES depression) |
| `population_raster` | `src/inputs/fetch_population.py` (WorldPop US 100 m) |
| `effect_size` | sourced default `0.93` — OR per +0.1 NDVI, Liu et al. 2023, *Environ. Res.* 231:116303 |
| `search_radius` | `300` m (set in `run_model.py`) |

Two of these are assumptions to revisit for a real analysis: the greening
scenario (a placeholder +0.05 NDVI) and the effect size (an odds ratio used as a
risk ratio).

Install (heavy — depends on GDAL). Per the [InVEST install
docs](https://invest.readthedocs.io/en/latest/installing.html), conda-forge is
recommended and is the only easy route on Apple Silicon Macs:
```bash
conda create -n invest -c conda-forge python=3.11 natcap.invest
conda activate invest
```
(`pip install natcap.invest` works only if a GDAL toolchain is already present.)

**Run everything at once.** With the `snapp` env active and Earth Engine
authenticated (see setup), the whole pipeline runs in one command:
```bash
bash run_pipeline.sh              # all five steps, in order
bash run_pipeline.sh --validate   # build inputs, then only validate the model
```
It stops at the first error; comment out a step in the script if its output
already exists (e.g. to avoid re-downloading). To run steps individually:

```bash
# greenness (ndvi_base) — pick ONE:
python src/sf_ndvi/composite_ndvi.py           # 300 m: composite the Copernicus dekads
python src/sf_ndvi/ndvi_sentinel2.py           # 10 m: Sentinel-2 via CDSE openEO (better)
python src/sf_ndvi/ndvi_gee.py                 # 30 m: Landsat JJAS p90 via Google Earth Engine

# AOI + baseline prevalence (depression) as one step:
python src/inputs/build_aoi_prevalence.py      # -> sf_aoi.gpkg, baseline_prevalence.gpkg

# population raster (uses a local file in _worldpop/ if present, else downloads):
python src/inputs/fetch_population.py

# greening scenario (ndvi_alt) from the baseline NDVI:
python src/inputs/make_ndvi_scenario.py                  # uniform +0.05, capped at 0.90

# effect_size has a sourced default (0.93, Liu et al. 2023); adjust in run_model.py if needed
python src/urban_mental_health/run_model.py --spec       # list inputs
python src/urban_mental_health/run_model.py --validate   # check inputs
python src/urban_mental_health/run_model.py              # run
```

Input builders (`src/inputs/`): `build_aoi_prevalence.py` pulls Census TIGER
tracts for SF and joins CDC PLACES depression prevalence into a `risk_rate`
field; `fetch_population.py` downloads the WorldPop US 100 m population raster,
clips it to the AOI, and reprojects it to meters (or pass `--pop` to use your own
file). Both write into `data/urban-mental-health/inputs/` with the exact
filenames `run_model.py` expects. If you use the Sentinel-2 NDVI, point
`ndvi_base` at `sf_ndvi_2024_s2_10m.tif`.

Data sources:

- **Greenness (NDVI):** Landsat via [Google Earth Engine](https://developers.google.com/earth-engine/datasets) (default) or [Copernicus NDVI 300 m / Sentinel-2 via CDSE](https://land.copernicus.eu/).
- **AOI:** [US Census TIGER/Line census tracts](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html).
- **Depression prevalence:** [CDC PLACES, census-tract 2024 release](https://data.cdc.gov/500-Cities-Places/) (dataset `cwsq-ngmh`, measure `DEPRESSION`).
- **Population:** [WorldPop "Global 2015–2030" (Global2), R2025A, listing id=135](https://hub.worldpop.org/geodata/listing?id=135) — constrained US 100 m population, per year 2015–2030 (default 2024). License: CC BY 4.0 — cite WorldPop.
- **Effect size:** Liu et al. (2023), *Environmental Research* 231:116303, [DOI 10.1016/j.envres.2023.116303](https://doi.org/10.1016/j.envres.2023.116303).

Caveat: the Copernicus NDVI here is 300 m — coarse for a residential-greenness
analysis (mental-health search radii are typically ≤300 m). Prefer 10 m
Sentinel-2 or 30 m Landsat NDVI for a real study; 300 m is fine for testing the
pipeline.

### meps — Medical Expenditure Panel Survey (MEPS-HC)

*How to obtain:* downloaded from the MEPS-HC Data Tools portal
(https://meps.ahrq.gov). Source files are in `data/meps/raw/`.

## Setup

1. Register a free CDSE account: https://dataspace.copernicus.eu
2. Add credentials:
   ```bash
   cp .env.example .env      # then edit .env with your CDSE username + password
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run the NDVI downloader

```bash
python src/sf_ndvi/download.py
```

**Heads-up on size:** OData can't subset spatially server-side, so each global
file (~a few hundred MB) is downloaded to `raw/`, clipped into `processed/`, then
deleted. Budget ~10–15 GB of temporary downloads; final SF outputs are a few KB
each. A lighter Sentinel Hub Process API version (server-side SF window) is
available on request.

## GitHub

The repo is hosted at
[github.com/Yingjie4Science/SNAPP](https://github.com/Yingjie4Science/SNAPP)
(default branch `main`). Day-to-day:

```bash
git add .
git commit -m "your message"
git push
```

`.env` and `data/` are gitignored, so credentials and large data never leave
your machine — a fresh clone reproduces the data by running the pipeline.

First-time clone on another machine:
```bash
git clone git@github.com:Yingjie4Science/SNAPP.git
# then follow "Development setup" to create the env and add .env
```

## Sources

- [NDVI 300m v2.0 product page (superseded)](https://land.copernicus.eu/en/products/vegetation/normalised-difference-vegetation-index-v2-0-300m)
- [NDVI 300m v3.0 product page (current)](https://land.copernicus.eu/en/products/vegetation/normalised-difference-vegetation-index-v3-0-300m)
- [CDSE OData API documentation](https://documentation.dataspace.copernicus.eu/APIs/OData.html)
- [Copernicus Data Space Ecosystem (registration)](https://dataspace.copernicus.eu/)
