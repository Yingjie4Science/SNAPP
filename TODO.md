# SNAPP — TODO / roadmap

_Updated 2026-07-30. Detailed U.S. decisions are in
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

- [ ] Decide whether to finish the national existing-greenness accounting run;
      SF already includes this comparison.
- [x] Export an exact platform environment lock and raw-input checksum manifest.
- [x] Add CI tests for national completeness, population reconciliation, and
      finite outputs.
- [ ] Decide whether regional wage-adjusted societal cost belongs in the main
      analysis or supplement.
- [ ] Resolve or explicitly retain the SF NDVI buffer edge warning.
- [ ] Apply the documented endpoint and causal-language caveats throughout the
      final manuscript.

## Later extensions

- [ ] National tract-level equity/SVI (current national result is county-level).
- [ ] Regional cost sensitivity using local wages for the productivity share.
- [ ] Alaska/Hawaii/territory-specific projections and source coverage.
- [ ] A one-command input manifest/rebuild workflow for a fresh clone.
