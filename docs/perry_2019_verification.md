# Hystad et al. (2019; mislabelled “Perry”) verification

## Bibliographic record

**Verified.** The paper referred to as “Perry 2019” in the discussion is:

Hystad, P., Payette, Y., Noisel, N., & Boileau, C. (2019). Green space
associations with mental health and cognitive function: Results from the Quebec
CARTaGENE cohort. *Environmental Epidemiology, 3*(1), e040.
https://doi.org/10.1097/EE9.0000000000000040

- PubMed: https://pubmed.ncbi.nlm.nih.gov/33778335/
- PubMed Central: https://pmc.ncbi.nlm.nih.gov/articles/PMC7952103/
- PMID: 33778335; PMCID: PMC7952103
- Published online 12 February 2019.
- Analytic cohort: 8,144 adults in urban Quebec, Canada.

The author is **Perry Hystad**; “Perry” is not the surname. Citations in the
manuscript and code should therefore use **Hystad et al. (2019)**.

## Table 1 transcription

The following lowest residential-NDVI-quartile values were checked against
Table 1:

| Depression definition | Lowest-NDVI-quartile count | Percent | p0 sensitivity value |
|---|---:|---:|---:|
| Health-record diagnosis | 234 | 11.5% | 0.115 |
| Self-reported doctor diagnosis | 192 | 9.6% | 0.096 |
| PHQ-9 score ≥10 | 130 | 6.4% | 0.064 |

These are three alternative outcome definitions, not mutually exclusive
categories. Their row-specific denominators can also differ because of missing
outcome data, and the printed percentages are rounded. Consequently:

- do not sum the counts;
- do not average the percentages;
- do not construct a weighted composite without participant-level overlap and
  missingness data.

The paper reports low correspondence between health-record and self-reported
doctor diagnoses (36% positive predictive value and 93% negative predictive
value). That directly supports keeping the definitions separate.

## Relationship to Liu et al. (2023)

Liu's NDVI forest plot includes three estimates labelled Hystad/Perry: two
PHQ-9 threshold outcomes and self-reported doctor-diagnosed depression. The
health-record prevalence in Hystad Table 1 is therefore useful because it is
the Hystad definition most similar to the diagnosis-based PLACES outcome, but it
is not a uniquely matched baseline risk for every study/outcome in Liu's pooled
OR.

## Decision for this project

The three Hystad values remain separate **outcome-definition sensitivity
anchors**. None is the primary U.S. p0. The primary p0 is derived from the
model's own CDC PLACES outcome, U.S. national-urban population, and harmonized
baseline NDVI distribution. This avoids transferring a single Quebec cohort's
age mix, health system, exposure distribution, and outcome ascertainment into
the national U.S. reference risk.

## Verification sources

- The PubMed record verifies title, authors, journal, date, cohort size, DOI,
  PMID, and PMCID.
- The open-access full article verifies the outcome definitions, cohort,
  Table 1 structure, and the low agreement between diagnosis measures.
- The publisher/PDF Table 1 transcription verifies the three Q1 counts and
  percentages listed above.
