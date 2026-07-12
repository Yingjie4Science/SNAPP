# SNAPP — TODO / roadmap

## Done
- [x] NDVI: Landsat JJAS p90 via GEE (`src/inputs/ndvi/ndvi_gee.py`); CDSE/Sentinel-2 backups.
- [x] Inputs: AOI + depression prevalence (local shp or CDC API), WorldPop population, greening scenario.
- [x] Health cost: pooled societal ~$21,280/case (Greenberg 2018/2019 + König meta-analysis), PubMed cross-checked.
- [x] Model runs end to end; sensitivity runner (effect_size × cost).
- [x] National scaffold (`run_city.py`, `run_national.sh`, EPSG:5070).
- [x] Repro: `config.yaml`, `pytest` smoke tests, results-summary script.

## Now / high priority
- [ ] **Adult-population correction** — re-run with `fetch_population.py --adult-fraction`
      so baseline cases use adults ≥18 (prevalence is adult). Confirms the ~8.5k figure.
- [ ] **Realistic greening scenario** — generators + data helpers all built
      (`fetch_nlcd_gee.py`, `scenario_lulc_masked.py`, `fit_tcc_ndvi.py`,
      `scenario_canopy_target.py`; see `docs/greening_scenarios.md`). Remaining:
      run them, pick a scenario, and set `config.yaml inputs.ndvi_alt`.
- [ ] **Interpret + QA** — run `summarize_results.py`; sanity-check totals and map per tract.

## Reproducibility / hygiene
- [ ] Lock the env: `conda env export --from-history > environment.lock.yml` (commit it).
- [ ] Wire remaining scripts to read `config.yaml` (currently: run_model + fetch_population).
- [ ] Add a `fetch_all_inputs` helper or data manifest so a fresh clone can rebuild `data/`.
- [ ] Move repo off Google Drive to a local clone (avoids git lock/corruption).
- [ ] Rotate the CDSE password (was briefly exposed); update `.env`.

## Later
- [ ] National run: build counties-in-metro AOI (`build_metro_counties.py`, ideally with
      your metro layer) + supply per-county NDVI, then `run_national.sh`.
- [ ] Regionalize cost (`--wage-factor`, MEPS region) for non-SF cities.
- [ ] CI (GitHub Actions) running `pytest` on push.
