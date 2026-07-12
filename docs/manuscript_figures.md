# Manuscript figures & tables (Nature Cities)

Generate everything (in the `snapp` env, after running the model / scenarios /
sensitivity):

```bash
python src/urban_mental_health/make_manuscript_figures.py
```

Outputs: `figures/manuscript/*.pdf` + `*.png` (300 dpi, Arial, colorblind-safe,
editable-text vector PDF) and `tables/Table*.{csv,md}`. Each figure regenerates
from the current model outputs, so re-run after the adult-population fix or a new
scenario. Draft captions below (fill in the final numbers from `tables/`).

## Figures

**Fig. 1 | Study area and model inputs, San Francisco.** (a) Baseline growing-
season NDVI (Landsat, 30 m). (b) Census-tract depression prevalence (CDC PLACES).
(c) Adult population (WorldPop, 100 m). Together these define greenness exposure,
the health baseline, and the exposed population.

**Fig. 2 | Preventable depression burden under greening.** Per-tract (a)
preventable depression cases per year and (b) avoided societal cost per year,
for the [scenario] greening scenario relative to baseline.

**Fig. 3 | Preventable burden by greening scenario.** Preventable cases (left
axis) and avoided societal cost (right axis) for each scenario (greenable,
LULC-masked, canopy-target), at central effect size and cost.

**Fig. 4 | Sensitivity of avoided cost.** Avoided societal cost (US$ M yr⁻¹)
across the exposure–response effect size (0.887 / 0.93 / 0.977) and the societal
cost per case ($17k / $21.3k / $23k), spanning the plausible range.

## Tables

**Table 1 | Model inputs and data sources.** Input, description, source, year
(static; `tables/Table1_data_sources.*`).

**Table 2 | Summary of preventable depression burden.** Central preventable
cases and avoided cost per year, with the effect-size sensitivity range
(computed from outputs; `tables/Table2_results_summary.*`).

## Notes for submission

- Nature Cities: figures at 88 mm (single) or 180 mm (double column); the script
  uses these widths. Submit the **PDF** (vector, editable text) versions.
- Palettes are colorblind-safe (YlGn/YlGnBu/cividis/magma). Check final contrast.
- Report results as a **range**, not a point (effect size + cost + scenario are
  the dominant uncertainties). Re-run with the adult-population correction before
  quoting final numbers.
