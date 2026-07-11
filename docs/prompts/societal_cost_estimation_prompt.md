# Reusable prompt — pooled, cross-validated societal cost-per-case estimate

Portable across LLMs. Fill the {PLACEHOLDERS}, then paste. Works best with a model
that has literature-search / web tools; if it has none, it will fall back to its
training knowledge (lower confidence — tell it to flag that).

---

## PROMPT

You are a health-economics research assistant. Produce a **defensible annual
{COST_TYPE: e.g. full societal} cost per {CASE_BASIS: e.g. prevalent} case of
{CONDITION: e.g. major depressive disorder (MDD)}** in **{GEOGRAPHY: e.g. the
United States}**, in **{TARGET_YEAR: e.g. 2024} {CURRENCY: e.g. USD}**, for use as
a `{PARAMETER_NAME: e.g. health_cost_rate}` in {USE_CASE: e.g. the InVEST Urban
Mental Health model}.

Do NOT rely on a single study. Pool multiple cost-of-illness (COI) studies and
cross-validate. Follow these steps and show your work:

1. **Search** the literature using every tool available to you (academic search
   connectors, PubMed/Europe PMC, web search). Run several query angles:
   "economic burden of {CONDITION} {GEOGRAPHY}", "cost of illness {CONDITION} per
   person", indirect/workplace/productivity cost, and "systematic review OR
   meta-analysis {CONDITION} cost". Prefer peer-reviewed sources.

2. **Select** studies that report a *national incremental (excess)* burden AND the
   size of the affected population, so a per-case figure can be derived. Include
   at least one systematic review/meta-analysis and, if possible, ≥2 studies with
   *different base years* for cross-validation. Note study type, base year, and
   the currency/base-year of the reported dollars.

3. **Derive per case**: per case = total incremental burden ÷ number of
   {GEOGRAPHY} {CASE_BASIS} cases. State the denominator and its source.

4. **Inflation-adjust** every per-case figure to {TARGET_YEAR} using a named index
   (e.g. BLS CPI-U annual averages) — state the index values and factors used.

5. **Pool**: take the mean of the per-case estimates from the most recent,
   methodologically-comparable studies. Use older vintages as a convergence check.
   Report the spread across studies and explain the main driver of any difference
   (e.g. denominator vs. real cost change).

6. **Decompose** the cost into components (direct medical, indirect/workplace
   absenteeism + presenteeism, suicide-related, household/caregiver, comorbidity)
   with each component's share, if the sources report it.

7. **Reconcile** with any directly-observed narrower figure the user has (e.g. a
   healthcare-only claims/expenditure value): explain why the societal total is
   larger and which component the narrow figure maps to.

8. **Caveats**: state the costing basis (prevalence- vs incidence-based; per-
   prevalent vs per-treated case), comorbidity/attribution assumptions and their
   effect on the range, whether one research group dominates the evidence, and
   geographic transferability (e.g. local wages shift wage-driven components).

**Deliverables:**
- A **recommended central value** plus an explicit **low–high sensitivity range**,
  with one-line justification for each bound.
- A **data table** of the studies pooled: citation, base year, total burden,
  currency-year, population denominator, per-case as-reported, per-case in
  {TARGET_YEAR} {CURRENCY}, and whether it was pooled vs. convergent-only.
- A short **methods** paragraph (search + inclusion + inflation + pooling).
- **Full citations** with DOIs/links. Cite every number to its source; if a value
  is your own derivation (e.g. total ÷ population), label it as derived.
- If you lacked live search tools, say so and lower your stated confidence.

Be transparent about uncertainty: present the **range**, not just the point
estimate, as the finding.

---

## Notes for reuse

- Swap `{CONDITION}` / `{GEOGRAPHY}` / `{TARGET_YEAR}` to retarget (e.g. anxiety,
  diabetes; UK; 2025). The method is condition-agnostic.
- For a **regional/local** figure, add: "Adjust wage-driven components by a local
  wage/cost-of-living factor and state the factor."
- Example output this prompt produced for MDD/US/2024: pooled ≈ $21,280/case
  (range ~$17k–$23k), from the Greenberg COI series (2010/2018/2019 base years)
  cross-validated with the König 2019 meta-analysis. See
  `docs/societal_cost_of_depression.md`.
