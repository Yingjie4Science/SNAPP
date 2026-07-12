**Table 1.** Model inputs and data sources.

| Input | Description | Source | Year |
|---|---|---|---|
| Greenness (NDVI) | Landsat C2 L2, JJAS 90th percentile, 30 m | USGS/GEE | 2024 |
| Greening scenarios | LULC-masked / canopy-target / greenable | NLCD Land Cover + TCC | 2021/2024 |
| AOI + population units | Census tracts; WorldPop adult population 100 m | Census TIGER; WorldPop R2025A | 2024 |
| Depression prevalence | CDC PLACES crude prevalence (risk_rate) | CDC PLACES | 2021 |
| Effect size | RR 0.93 per +0.1 NDVI (0.887-0.977) | Liu et al. 2023 (Environ. Res.) | 2023 |
| Societal cost / case | US$21,280 (range 17,000-23,000) | Greenberg 2018/2019; Konig 2019 meta-analysis | 2024 USD |
| Model | InVEST Urban Mental Health | natcap.invest >=3.19 | - |
