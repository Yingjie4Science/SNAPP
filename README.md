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
├── config.yaml               # central parameters (CRS, effect size, cost, scenario…)
├── TODO.md                   # roadmap / open items
├── environment.yml           # conda env spec (recommended setup)
├── requirements.txt          # pip alternative
├── tests/                    # pytest smoke tests (cost math, config, scenario)
├── run_pipeline.sh           # SF: run all steps end to end
├── run_national.sh           # national: loop config/cities.csv, run per city
├── config/cities.csv         # list of US cities (place GEOIDs) for the national run
├── docs/                     # societal-cost synthesis, cost_studies.csv, scaling notes
├── .vscode/                  # shared editor config (interpreter + extensions)
├── src/
│   ├── inputs/                        # everything that builds a model input
│   │   ├── ndvi/                      # greenness: baseline NDVI + greening scenarios
│   │   │   ├── ndvi_gee.py            # 30 m Landsat JJAS p90 NDVI via GEE (ACTIVE baseline)
│   │   │   ├── make_ndvi_scenario.py  # ndvi_alt: uniform / greenable
│   │   │   ├── scenario_lulc_masked.py   # ndvi_alt: LULC-masked greening (primary)
│   │   │   ├── scenario_canopy_target.py # ndvi_alt: per-tract canopy/NDVI target
│   │   │   ├── fetch_nlcd_gee.py      # NLCD Land Cover + Tree Canopy Cover (GEE)
│   │   │   ├── fit_tcc_ndvi.py        # regress tract NDVI ~ canopy% -> slope/intercept
│   │   │   └── alternatives/          # backup NDVI sources (Copernicus/CDSE)
│   │   │       ├── download.py            # Copernicus NDVI 300 m via CDSE
│   │   │       ├── composite_ndvi.py      # composite the Copernicus dekads
│   │   │       └── ndvi_sentinel2.py      # 10 m Sentinel-2 via CDSE openEO
│   │   ├── build_aoi_prevalence.py    # AOI + depression risk_rate (local shp or CDC API)
│   │   ├── fetch_population.py        # WorldPop US 100 m -> adult pop, clip to AOI
│   │   └── estimate_health_cost.py    # societal (Greenberg) or direct (MEPS)
│   ├── national/
│   │   └── run_city.py                # run the model for ONE city (EPSG:5070)
│   └── urban_mental_health/
│       ├── run_model.py               # runs the InVEST Urban Mental Health model
│       ├── run_scenarios.py           # run all greening scenarios -> comparison CSV
│       ├── run_sensitivity.py         # effect_size x cost sensitivity grid -> CSV
│       ├── summarize_results.py       # totals, QA checks, per-tract map
│       └── make_manuscript_figures.py # publication figures + tables (Nature Cities)
├── data/                     # gitignored — never pushed to GitHub
│   └── urban-mental-health/
│       ├── raw/              # raw source data
│       │   ├── cdc_places/  # depression prevalence shapefile -> risk_rate
│       │   ├── meps/        # MEPS medical-expenditure files -> health_cost_rate
│       │   └── nlcd/        # NLCD land cover + tree canopy (greening scenarios)
│       ├── inputs/           # model-ready inputs (built by the src/ scripts)
│       └── workspace*/       # model outputs (base, sensitivity, scenarios, national)
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

### Config, tests, reproducibility

- **`config.yaml`** is the single source of truth for parameters (CRS, effect
  size, cost basis, scenario, adult fraction). `run_model.py` and the pipeline
  read it; edit there rather than in individual scripts.
- **Tests:** `pytest` (from the repo root) runs smoke tests for the cost math,
  config integrity, and scenario capping.
- **Lock the environment** for exact reproducibility, and commit the lock:
  ```bash
  conda env export --from-history > environment.lock.yml
  ```

## Datasets

### urban-mental-health — InVEST Urban Mental Health model

Runner: `src/urban_mental_health/run_model.py`. Uses the `natcap.invest` Python
API (`urban_mental_health.execute(args)`) to estimate preventable mental-health
cases (and optional societal cost) from residential greenness.

The model compares a **baseline vs. an alternate (greening) scenario** — either
two NDVI rasters (`model_option='ndvi'`) or two LULC rasters. Data flows
**`raw/` → (scripts) → `inputs/` → (model) → `workspace/`**:

- `raw/cdc_places/` — depression prevalence shapefile → `baseline_prevalence_vector` (`risk_rate`)
- `raw/meps/` — MEPS medical-expenditure files → `health_cost_rate` (societal cost per case)
- `inputs/` — model-ready files the `src/` scripts build; `workspace/` — model outputs

| Model input | Built by | Raw source |
|---|---|---|
| `ndvi_base` | `src/inputs/ndvi/ndvi_gee.py` | Landsat via Google Earth Engine |
| `ndvi_alt` | `src/inputs/ndvi/make_ndvi_scenario.py` | derived from `ndvi_base` |
| `aoi_path` | `src/inputs/build_aoi_prevalence.py` | Census TIGER tracts |
| `baseline_prevalence_vector` (`risk_rate`) | `src/inputs/build_aoi_prevalence.py` | CDC PLACES — `raw/cdc_places/` |
| `population_raster` | `src/inputs/fetch_population.py` | WorldPop US 100 m |
| `health_cost_rate` | `src/inputs/estimate_health_cost.py` | societal ~$21,280/case (pooled Greenberg 2018 & 2019) default, or `--basis direct` MEPS ~$1,438 |
| `effect_size` | sourced default `0.93` | Liu et al. 2023, *Environ. Res.* 231:116303 |
| `search_radius` | `300` m (set in `run_model.py`) | — |

Assumptions to revisit for a real analysis: the greening scenario (placeholder
+0.05 NDVI), the effect size (an odds ratio used as a risk ratio), and
`health_cost_rate` — now the **societal** ~$21,280/case (pooled; range ~$17k–$23k;
US-national, comorbidity attribution debatable). Use `--basis direct` for a
conservative healthcare-only figure. Details: `docs/societal_cost_of_depression.md`.

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
# greenness (ndvi_base) — active route:
python src/inputs/ndvi/ndvi_gee.py                 # 30 m: Landsat JJAS p90 via Google Earth Engine
# backups (see src/inputs/ndvi/alternatives/): Copernicus 300 m or Sentinel-2 via CDSE

# AOI + baseline prevalence (depression): local CDC shapefile by default, or --source api
python src/inputs/build_aoi_prevalence.py      # -> aoi.gpkg, baseline_prevalence.gpkg

# population raster (adult-scaled: prevalence is adult, so scale total pop to >=18):
python src/inputs/fetch_population.py --adult-fraction 0.86   # SF adult share

# greening scenario (ndvi_alt) from the baseline NDVI:
python src/inputs/ndvi/make_ndvi_scenario.py                  # uniform +0.05, capped at 0.90

# health_cost_rate (writes inputs/health_cost_rate.txt + components.csv, read by the model):
python src/inputs/estimate_health_cost.py                # societal ~$21,280 pooled (default)
# python src/inputs/estimate_health_cost.py --basis direct   # MEPS direct medical (~$1,438)

# effect_size has a sourced default (0.93, Liu et al. 2023); adjust in run_model.py if needed
python src/urban_mental_health/run_model.py --spec       # list inputs
python src/urban_mental_health/run_model.py --validate   # check inputs
python src/urban_mental_health/run_model.py              # run

# compare greening scenarios (runs the model for each ndvi_alt in config.yaml scenarios:)
python src/urban_mental_health/run_scenarios.py

# sensitivity: effect_size (0.887/0.93/0.977) x cost ($17k/$21.3k/$23k) -> summary CSV
python src/urban_mental_health/run_sensitivity.py

# summarize + QA the outputs -> docs/results_summary.md (add --map for a choropleth)
python src/urban_mental_health/summarize_results.py
```

Input builders (`src/inputs/`): `build_aoi_prevalence.py` builds the SF tract AOI
and a `risk_rate` field — by default from the local CDC shapefile in
`raw/cdc_places/` (2021), or `--source api` for live Census TIGER + CDC PLACES
2024; `fetch_population.py` uses the WorldPop US 100 m raster (local file in
`_worldpop/` or download), clips to the AOI, and reprojects to meters;
`estimate_health_cost.py` writes the cost per case to `health_cost_rate.txt` —
default **societal** (~$21,280, pooled across Greenberg 2018 & 2019, with a `health_cost_components.csv`
breakdown) or `--basis direct` for the MEPS direct-medical figure (~$1,438). See
`docs/societal_cost_of_depression.md`. All write into `data/urban-mental-health/inputs/` with the
exact filenames `run_model.py` expects.

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

### Raw source data (`data/urban-mental-health/raw/`)

- **`cdc_places/`** — CDC PLACES depression prevalence shapefile
  (`prevalence_rate_usa_2021.shp`), the source for the model's `risk_rate`.
  From [CDC PLACES](https://www.cdc.gov/places/).
- **`meps/`** — Medical Expenditure Panel Survey (MEPS-HC) medical-conditions
  files, the source for `health_cost_rate` (societal cost per depression case).
  From the [MEPS-HC Data Tools portal](https://meps.ahrq.gov).

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

## Scaling to a national multi-city study

The SF pipeline generalizes to all US cities. `src/national/run_city.py` runs the
model for one Census **place** (by GEOID), using a CONUS-wide CRS (**EPSG:5070**),
selecting prevalence tracts by spatial intersection, windowed-clipping the
national WorldPop raster, and writing to a per-city workspace.
`run_national.sh` loops `config/cities.csv`:

```bash
bash run_national.sh data/national/places.gpkg data/national/ndvi
# args: <national places layer>  <dir of per-city <GEOID>_ndvi.tif>
```

What you provide once: a national "places" polygon layer, and per-city NDVI
rasters from the GEE city loop (your Code Editor script already iterates cities).
Prevalence (national CDC tract shapefile), population (WorldPop US), cost, and
effect size are already national. Full rationale and steps:
`docs/scaling_to_national.md`.

## Backup NDVI route (Copernicus / CDSE)

The active NDVI source is `src/inputs/ndvi/ndvi_gee.py`. If you ever need the
Copernicus route instead, `src/inputs/ndvi/alternatives/download.py` downloads the
NDVI 300 m global 10-daily files and clips them to SF, then
`alternatives/composite_ndvi.py` composites them into one `ndvi_base` raster.

**Heads-up on size:** OData can't subset spatially server-side, so each global
file (~a few hundred MB) is downloaded to `raw/`, clipped into `processed/`, then
deleted. Budget ~10–15 GB of temporary downloads; final SF outputs are a few KB
each.

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
