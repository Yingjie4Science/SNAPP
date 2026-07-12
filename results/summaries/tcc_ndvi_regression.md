# TCC -> NDVI regression

Per-tract mean NDVI on mean NLCD Tree Canopy Cover (%), n=243, R^2=0.696:

    NDVI = 0.07464 + 0.01892 * canopy_percent

Use in the canopy-target scenario (example, 30% goal):

    python src/inputs/ndvi/scenario_canopy_target.py --canopy-target 30 --tcc-slope 0.01892 --tcc-intercept 0.07464
