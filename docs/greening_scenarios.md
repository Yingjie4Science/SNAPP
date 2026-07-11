# Designing a realistic greening scenario (ndvi_alt)

The model compares baseline NDVI against an **alternate (greening) scenario**.
The result scales strongly with this choice, so a defensible scenario matters
more than almost any other input. The current default (`make_ndvi_scenario.py`,
uniform +0.05 everywhere, capped 0.90) is a **placeholder** — it greens water,
rooftops, and already-green parks alike, which isn't physically meaningful.

## What makes a scenario credible

1. **Only green what's greenable** — exclude water, buildings, and pixels already
   near the vegetation ceiling; concentrate change where it's plausible
   (streets, parking, bare/impervious residential land).
2. **Tie the magnitude to a real target** — a canopy % goal or a known program,
   not an arbitrary Δ.
3. **Put change where people live** — the model weights by population, so
   greening residential/low-income low-NDVI areas yields (and equitably
   distributes) the most benefit.
4. **State the counterfactual horizon** — "full build-out of plan X," or "town
   reaches the 30% canopy target."

## Options, roughly increasing realism

| # | Scenario | How to build | Pros / cons |
|---|---|---|---|
| A | **Uniform +Δ** (current) | add Δ to all pixels | trivial; unrealistic (greens water/roofs) |
| B | **Greenable-only +Δ** | `make_ndvi_scenario.py --mode greenable --target 0.6` — raise only pixels below a threshold | simple, already supported; ignores land cover |
| C | **LULC-masked greening** | switch to `model_option='lulc'`: reclassify impervious/bare classes toward vegetated NDVI via the LULC attribute table | uses real land cover; needs an LULC raster + NDVI lookup |
| D | **Canopy-target** | raise NDVI so each tract hits a tree-canopy goal (e.g. 30%), using NLCD Tree Canopy Cover (TCC) → NDVI mapping | policy-relevant, matches your NLCD-TCC alignment; needs a TCC→NDVI relationship |
| E | **Parcel/plan-based** | apply NDVI gains only on parcels in an actual urban-forestry/greening plan | most defensible; needs local plan geometry |

## Recommendation

**Start with C (LULC-masked greening) as the primary scenario, and D
(canopy-target) as the policy headline.** Rationale:

- Your NDVI is already built to align with **NLCD Tree Canopy Cover** (your GEE
  script filters to June–Sept for exactly this reason), so a canopy-based
  scenario is a natural, well-grounded next step and directly interpretable by
  planners ("reach 30% canopy").
- LULC masking (C) prevents the biggest artifact (greening water/rooftops) with
  data that's readily available (NLCD Land Cover), and the InVEST model *natively*
  supports the LULC option — so it's a clean switch, not a hack.
- Keep **B (greenable-only)** as a quick, data-light sensitivity variant.

Suggested concrete default: **NLCD-based, raise NDVI on developed-open /
low-intensity / barren pixels toward the tract's 75th-percentile NDVI (a locally
achievable "green" level), capped at 0.85; leave water, wetlands, and high-canopy
pixels unchanged.** Report results against a 30% canopy-target headline.

## Scripts (all three are implemented)

| Scenario | Script | You still supply |
|---|---|---|
| B — greenable-only (quick sensitivity) | `src/inputs/make_ndvi_scenario.py --mode greenable` | nothing |
| C — LULC-masked (primary) | `src/inputs/scenario_lulc_masked.py --lulc <nlcd.tif>` | an NLCD Land Cover raster (free, [mrlc.gov](https://www.mrlc.gov/data)) |
| D — canopy-target (policy headline) | `src/inputs/scenario_canopy_target.py --target-ndvi 0.60` (or `--canopy-target 30 --tcc-slope … --tcc-intercept …`) | a target NDVI, or a TCC→NDVI regression (fit tract-mean NDVI on NLCD TCC) |

Each writes an `ndvi_alt` raster to `data/urban-mental-health/inputs/`
(`sf_ndvi_scenario_lulc.tif` / `sf_ndvi_scenario_canopy.tif` / `sf_ndvi_scenario.tif`).
Point the model at the one you want via `config.yaml → inputs.ndvi_alt`, then run
`run_model.py`.

Getting the data is now scripted too (via GEE, like the NDVI step):

```bash
# 1. fetch NLCD Land Cover (for C) and Tree Canopy Cover (for D):
python src/inputs/fetch_nlcd_gee.py

# 2C. LULC-masked scenario:
python src/inputs/scenario_lulc_masked.py --lulc data/urban-mental-health/inputs/nlcd_landcover_sf.tif

# 2D. fit TCC->NDVI, then run the canopy-target scenario with the printed slope/intercept:
python src/inputs/fit_tcc_ndvi.py          # writes docs/tcc_ndvi_regression.md + prints the command
python src/inputs/scenario_canopy_target.py --canopy-target 30 --tcc-slope <s> --tcc-intercept <i>
```

`fit_tcc_ndvi.py` regresses per-tract mean NDVI on mean canopy% and reports
slope/intercept + R²; plug those into the canopy-target scenario.
