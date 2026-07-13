# Equity analysis — who benefits from greening

_237 tracts matched to ACS 2023 income; 236 matched to CDC/ATSDR 2022 SVI._

## Interpretation for decisions

- **Income:** CI **+0.020** — no material gradient detected.
- **Social vulnerability (SVI):** CI **-0.028** — benefits concentrate in less socially vulnerable neighborhoods (equity concern).
- **Bottom line:** the result describes the distribution of modeled benefit, not whether investments reach residents who need them most. Use it alongside project siting, community engagement, and anti-displacement safeguards.

CI ranges from −1 to +1; values within ±0.02 are treated here as no material gradient. For income, negative means benefit is concentrated among lower-income tracts. For SVI, positive means benefit is concentrated among more vulnerable tracts.

![Concentration curves](../figures/equity_concentration_curves.png)
<sub>Curves above the diagonal indicate concentration among the lower end of the rank. For income that means lower income; for SVI that means lower vulnerability.</sub>

## By income decile (1 = lowest income)

| decile | mean tract income | preventable cases / 1,000 adults | % of total cases |
|---:|---:|---:|---:|
| 1 | $38,433 | 7.7 | 7.4% |
| 2 | $85,502 | 5.9 | 9.3% |
| 3 | $106,134 | 16.5 | 9.8% |
| 4 | $120,470 | 5.8 | 10.3% |
| 5 | $139,726 | 5.5 | 10.4% |
| 6 | $153,816 | 5.9 | 11.1% |
| 7 | $169,228 | 5.7 | 10.8% |
| 8 | $185,231 | 6.3 | 10.6% |
| 9 | $209,746 | 6.5 | 9.9% |
| 10 | $243,295 | 6.3 | 10.5% |

## By SVI decile (1 = least vulnerable)

| decile | mean CDC SVI percentile | preventable cases / 1,000 adults | % of total cases |
|---:|---:|---:|---:|
| 1 | 0.062 | 16.6 | 9.6% |
| 2 | 0.154 | 6.7 | 10.8% |
| 3 | 0.268 | 6.4 | 11.1% |
| 4 | 0.378 | 6.1 | 9.3% |
| 5 | 0.461 | 5.9 | 12.9% |
| 6 | 0.539 | 7.0 | 9.8% |
| 7 | 0.628 | 6.0 | 9.9% |
| 8 | 0.709 | 5.0 | 9.6% |
| 9 | 0.791 | 5.8 | 8.9% |
| 10 | 0.940 | 6.2 | 8.1% |

## Method and limits

Population-weighted health concentration indices use preventable cases per adult, not total cases, so large tracts do not mechanically dominate. Income uses ACS 2023 median household income. CDC/ATSDR 2022 SVI uses 16 ACS social factors across four themes; its overall percentile (RPL_THEMES) is ranked nationally, so it is a broader deprivation lens than income alone.

_Sources: Kakwani et al. (1997); CDC/ATSDR Social Vulnerability Index 2022; Wu et al. (2026)._
