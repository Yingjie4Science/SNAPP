# SNAPP — TODO / roadmap

_Updated 2026-08-01. Detailed U.S. decisions are in
`docs/us_case_status.md`._

## Completed

- [x] SF and national model pipelines with reproducible `config.yaml`.
- [x] Defensible 2024 societal cost: $21,280/case; $17,000–$23,000 range.
- [x] Nine SF investment scenarios plus existing-greenness accounting case in
      one report, with explicit legends and common denominators.
- [x] SF adult-population calibration and complete rerun.
- [x] SF income, SVI, ICE, spatial clustering, bootstrap, allocation, and
      exposure-radius sensitivity.
- [x] Locked national AOI: 1,167 counties.
- [x] Six missing Kentucky exports recovered and 56 out-of-AOI files
      quarantined.
- [x] All national NDVI harmonized to aligned 90 m EPSG:5070 grids.
- [x] Full-read NDVI audit including unmasked non-finite-cell detection.
- [x] Complete ACS 2023 adult targets and CDC/ATSDR 2022 county SVI.
- [x] Locked national low-NDVI-quartile p0 = 0.191045 and RR = 0.943436.
- [x] Florida-only official PLACES 2022 temporal bridge for null 2023 values.
- [x] Hystad et al. (2019) citation and outcome counts verified.
- [x] National primary and alternative greening scenarios for all counties.
- [x] National SVI equity analysis with bootstrap intervals.
- [x] National 250/300/500/1,000 m radius sensitivity and final fail-closed QA.

## Remaining before manuscript freeze

- [x] **HIGH — Finish the national existing-greenness accounting run.** This
      makes the national and SF reports structurally comparable and distinguishes
      the accounting value of current greenness from feasible new investment.
      All 1,167 counties pass completeness, population-reconciliation, and
      finite-output QA; the accounting estimate is 12,733,902 cases/year.
- [x] **HIGH — Export an exact environment lock and raw-input checksum
      manifest.** These are necessary to prove which software and large,
      gitignored inputs produced the final numbers and to detect silent data or
      dependency drift during review or reproduction.
- [x] **HIGH — Add CI tests for national completeness, population
      reconciliation, and finite outputs.** These are necessary because a
      partial or numerically corrupted 1,167-county rerun can otherwise look
      superficially complete when only aggregate files are reviewed.
- [x] **MEDIUM — Place regional wage-adjusted societal cost in the supplement.**
      The decision is necessary before freeze because wage adjustment affects
      geographic monetary comparisons, but it does not change preventable cases
      and adds assumptions beyond the national cost evidence used in the main
      analysis.
- [x] **HIGH — Explicitly retain and quantify the SF NDVI buffer edge warning.**
      The model needs NDVI around each populated cell; the current raster misses
      part of the northern/eastern 300 m buffer. Only 0.0916% of adults lack full
      extent coverage, so this is retained as a small limitation rather than a
      blocker (`results/summaries/sf_ndvi_buffer_audit.md`).
- [ ] **HIGH — Apply the documented endpoint and causal-language caveats
      throughout the final manuscript.** **On hold by request.**

## Later extensions

- [ ] National tract-level equity/SVI (current national result is county-level).
      **On hold.**
- [ ] Regional cost sensitivity using local wages for the productivity share.
      **On hold; supplement placement is decided, computation remains optional.**
- [ ] Alaska/Hawaii/territory-specific projections and source coverage.
      **On hold.**
- [ ] A one-command input manifest/rebuild workflow for a fresh clone.
      **On hold.**
