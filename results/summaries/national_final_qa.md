# National final QA

| Scenario | Radius | Status | Counties | Missing | Bad numeric | Max adult-pop error | Cases/year |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform_005 | 300 | pass | 1167 | 0 | 0 | 0.0 | 1,264,304 |
| proportional_10pct | 300 | pass | 1167 | 0 | 0 | 0.0 | 1,334,035 |
| greenable_005 | 300 | pass | 1167 | 0 | 0 | 0.0 | 670,172 |
| best_potential_p95 | 300 | pass | 1167 | 0 | 0 | 0.0 | 6,693,690 |
| uniform_005 | 250 | pass | 1167 | 0 | 0 | 0.0 | 1,264,303 |
| uniform_005 | 500 | pass | 1167 | 0 | 0 | 0.0 | 1,241,075 |
| uniform_005 | 1000 | pass | 1167 | 0 | 0 | 0.0 | 1,217,851 |

A passing row requires exactly 1,167 unique expected counties, finite case/cost/rate values, non-negative cases, positive adult population, and county population totals within one person of ACS 2023 targets.
