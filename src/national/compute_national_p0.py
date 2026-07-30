#!/usr/bin/env python3
"""Calculate and lock the U.S. national-urban low-NDVI-quartile p0.

The OR-to-RR conversion requires the outcome prevalence in the reference
exposure group.  This script defines that group reproducibly as tracts in the
population-weighted lowest quartile of baseline NDVI across the 1,167-county
national urban AOI.

For each county, WorldPop supplies the within-county population pattern and an
ACS lookup supplies the exact adult-population total.  CDC PLACES supplies
tract depression prevalence.  Population-weighted mean NDVI is calculated for
each tract, the national weighted 25th percentile is found, and p0 is the
adult-population-weighted PLACES prevalence among tracts at or below it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src" / "inputs"))
from compute_p0 import _weighted_quantile, update_config  # noqa: E402
from effect_size import or_to_rr  # noqa: E402

LOGGER = logging.getLogger("compute_national_p0")


def read_adult_targets(path: Path, expected_geoids: set[str]) -> pd.DataFrame:
    targets = pd.read_csv(path, dtype={"GEOID": str})
    required = {"GEOID", "population_adult"}
    missing_columns = required - set(targets.columns)
    if missing_columns:
        raise ValueError(f"{path} is missing columns {sorted(missing_columns)}")
    targets["GEOID"] = targets["GEOID"].str.zfill(5)
    targets["population_adult"] = pd.to_numeric(
        targets["population_adult"], errors="raise"
    )
    targets = targets[targets["GEOID"].isin(expected_geoids)].copy()
    observed = set(targets["GEOID"])
    missing = sorted(expected_geoids - observed)
    duplicate_count = int(targets["GEOID"].duplicated().sum())
    if missing or duplicate_count or len(targets) != len(expected_geoids):
        raise ValueError(
            "ACS adult-target coverage failure: "
            f"expected={len(expected_geoids)}, observed={len(targets)}, "
            f"missing={missing[:20]}, duplicates={duplicate_count}"
        )
    if (targets["population_adult"] <= 0).any():
        raise ValueError("ACS lookup includes non-positive adult population.")
    return targets.set_index("GEOID")


def county_tract_statistics(
    geoid: str,
    county_tracts: gpd.GeoDataFrame,
    ndvi_path: Path,
    adult_target: float,
    population_source: rasterio.io.DatasetReader,
) -> tuple[list[dict], dict]:
    with rasterio.open(ndvi_path) as ndvi_src:
        ndvi = ndvi_src.read(1, masked=True).filled(np.nan).astype("float64")
        shape = (ndvi_src.height, ndvi_src.width)
        transform = ndvi_src.transform
        crs = ndvi_src.crs

        tracts = county_tracts.to_crs(crs).reset_index(drop=True)
        tracts["_raster_id"] = np.arange(1, len(tracts) + 1, dtype="int32")
        tract_ids = rasterize(
            ((geom, ident) for geom, ident in zip(tracts.geometry, tracts["_raster_id"])),
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="int32",
        )

        population = np.full(shape, np.nan, dtype="float64")
        reproject(
            source=rasterio.band(population_source, 1),
            destination=population,
            src_transform=population_source.transform,
            src_crs=population_source.crs,
            src_nodata=population_source.nodata,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    pop_valid = np.isfinite(population) & (population > 0) & (tract_ids > 0)
    raw_total = float(population[pop_valid].sum())
    if raw_total <= 0:
        raise ValueError("no positive WorldPop cells overlap PLACES tracts")
    population *= adult_target / raw_total

    ndvi_valid = pop_valid & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    n_tracts = len(tracts)
    pop_all = np.bincount(
        tract_ids[pop_valid],
        weights=population[pop_valid],
        minlength=n_tracts + 1,
    )[1:]
    pop_ndvi = np.bincount(
        tract_ids[ndvi_valid],
        weights=population[ndvi_valid],
        minlength=n_tracts + 1,
    )[1:]
    ndvi_sum = np.bincount(
        tract_ids[ndvi_valid],
        weights=population[ndvi_valid] * ndvi[ndvi_valid],
        minlength=n_tracts + 1,
    )[1:]
    mean_ndvi = np.divide(
        ndvi_sum,
        pop_ndvi,
        out=np.full(n_tracts, np.nan),
        where=pop_ndvi > 0,
    )

    records = []
    for index, tract in tracts.iterrows():
        records.append(
            {
                "county_geoid": geoid,
                "tract_geoid": str(tract["GEOID"]),
                "places_depression_prevalence": float(tract["risk_rate"]),
                "places_prevalence_source": str(tract["_risk_source"]),
                "adult_population": float(pop_all[index]),
                "ndvi_covered_adult_population": float(pop_ndvi[index]),
                "population_weighted_mean_ndvi": float(mean_ndvi[index]),
            }
        )
    covered = float(pop_ndvi.sum())
    return records, {
        "GEOID": geoid,
        "adult_target": adult_target,
        "allocated_adults": float(pop_all.sum()),
        "ndvi_covered_adults": covered,
        "ndvi_population_coverage": covered / adult_target,
        "tract_count": n_tracts,
    }


def write_report(
    path: Path,
    p0: float,
    threshold: float,
    rr: tuple[float, float, float],
    tracts: pd.DataFrame,
    counties: pd.DataFrame,
    quantile: float,
) -> None:
    eligible = tracts["population_weighted_mean_ndvi"].notna() & (
        tracts["ndvi_covered_adult_population"] > 0
    )
    selected = eligible & (
        tracts["population_weighted_mean_ndvi"] <= threshold
    )
    overall_p0 = np.average(
        tracts.loc[eligible, "places_depression_prevalence"],
        weights=tracts.loc[eligible, "ndvi_covered_adult_population"],
    )
    selected_share = (
        tracts.loc[selected, "ndvi_covered_adult_population"].sum()
        / tracts.loc[eligible, "ndvi_covered_adult_population"].sum()
    )
    coverage = counties["ndvi_covered_adults"].sum() / counties["adult_target"].sum()
    text = f"""# National lowest-NDVI-quartile baseline risk (p0)

## Locked primary estimate

- **p0: {p0:.6f}**
- Reference group: whole tracts at or below the population-weighted national
  urban NDVI {quantile:.0%} threshold ({threshold:.6f} mean NDVI).
- Realized reference population share: {selected_share:.3%}. Whole-tract
  assignment can differ slightly from exactly {quantile:.0%} at the threshold.
- Converted Liu et al. (2023) RR per +0.1 NDVI:
  **{rr[0]:.6f}** (OR-CI conversion: {rr[1]:.6f}–{rr[2]:.6f}).

## Data and QA

- AOI counties: {len(counties):,}
- Eligible PLACES tracts: {int(eligible.sum()):,}
- Reference-group tracts: {int(selected.sum()):,}
- ACS adult population represented: {counties["adult_target"].sum():,.0f}
- Adult population with valid NDVI: {counties["ndvi_covered_adults"].sum():,.0f}
  ({coverage:.4%})
- Overall population-weighted PLACES prevalence, shown only as a convergence
  check: {overall_p0:.6f}
- Florida temporal bridge: {int((tracts["places_prevalence_source"] == "places_2022_florida_bridge").sum()):,}
  matched tracts. CDC's 2023 PLACES release has null measures for every Florida
  tract; the immediately preceding 2022 release uses the same outcome and 2015
  tract geography.

## Decision

This is the primary U.S. p0 because the prevalence definition (CDC PLACES),
population universe (adults), geography (the national study AOI), and exposure
distribution (the harmonized baseline NDVI) match the model. Hystad et al.
(2019) lowest-quartile values are retained as outcome-definition sensitivity
anchors, not pooled or averaged into the primary p0.

## Method

Within each county, WorldPop supplies relative spatial weights and the official
ACS 2023 five-year B01001 table supplies the exact age-18+ total. The calibrated
population is aggregated to CDC PLACES tracts on each county's harmonized 90 m
NDVI grid. Tracts are ranked by population-weighted mean NDVI nationally; p0 is
the population-weighted PLACES prevalence among tracts in the lowest weighted
quartile. The resulting p0 and full-precision OR-to-RR conversions are written
to `config.yaml`.
"""
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regions",
        type=Path,
        default=BASE_DIR / "data/national/counties_gee_upload/counties.shp",
    )
    parser.add_argument("--prevalence", type=Path, required=True)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument(
        "--ndvi-dir", type=Path, default=BASE_DIR / "data/national/ndvi_90m"
    )
    parser.add_argument(
        "--adult-population",
        type=Path,
        default=BASE_DIR / "config/adult_population.csv",
    )
    parser.add_argument(
        "--florida-places-bridge",
        type=Path,
        default=BASE_DIR / "config/places_florida_2022.csv",
        help="Official PLACES 2022 tract depression values used only where the "
        "2023 release is null for Florida.",
    )
    parser.add_argument("--quantile", type=float, default=0.25)
    parser.add_argument("--no-write-config", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if not 0 < args.quantile < 1:
        raise SystemExit("--quantile must be between 0 and 1")
    for path in (
        args.regions,
        args.prevalence,
        args.population,
        args.adult_population,
        args.florida_places_bridge,
    ):
        if not path.exists():
            raise SystemExit(f"Missing required input: {path}")

    regions = gpd.read_file(args.regions)
    regions["GEOID"] = regions["GEOID"].astype(str).str.zfill(5)
    expected_geoids = set(regions["GEOID"])
    targets = read_adult_targets(args.adult_population, expected_geoids)

    tracts = gpd.read_file(args.prevalence)
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)
    tracts["county_geoid"] = tracts["GEOID"].str[:5]
    tracts["risk_rate"] = pd.to_numeric(tracts["DEPRESS"], errors="coerce") / 100
    tracts["_risk_source"] = "places_2023_brfss_2021"
    florida = pd.read_csv(
        args.florida_places_bridge, dtype={"tractfips": str}
    )
    florida["tractfips"] = florida["tractfips"].str.zfill(11)
    florida_risk = (
        pd.to_numeric(florida["depression_crudeprev"], errors="coerce") / 100
    )
    bridge = dict(zip(florida["tractfips"], florida_risk))
    is_florida_missing = tracts["GEOID"].str.startswith("12") & tracts[
        "risk_rate"
    ].isna()
    tracts.loc[is_florida_missing, "risk_rate"] = tracts.loc[
        is_florida_missing, "GEOID"
    ].map(bridge)
    bridge_matched = is_florida_missing & tracts["risk_rate"].notna()
    tracts.loc[bridge_matched, "_risk_source"] = "places_2022_florida_bridge"
    LOGGER.info(
        "Florida PLACES bridge matched %d/%d null 2023 geometries.",
        int(bridge_matched.sum()),
        int(is_florida_missing.sum()),
    )
    tracts = tracts[
        tracts["county_geoid"].isin(expected_geoids)
        & tracts["risk_rate"].between(0, 1, inclusive="both")
        & tracts.geometry.notna()
    ].copy()
    grouped = {geoid: frame for geoid, frame in tracts.groupby("county_geoid")}

    tract_records: list[dict] = []
    county_records: list[dict] = []
    failures: list[str] = []
    with rasterio.open(args.population) as pop_source:
        for number, geoid in enumerate(sorted(expected_geoids), 1):
            ndvi_path = args.ndvi_dir / f"{geoid}_ndvi.tif"
            try:
                if geoid not in grouped:
                    raise ValueError("no valid PLACES tracts")
                if not ndvi_path.exists():
                    raise ValueError(f"missing NDVI {ndvi_path.name}")
                records, county = county_tract_statistics(
                    geoid,
                    grouped[geoid],
                    ndvi_path,
                    float(targets.loc[geoid, "population_adult"]),
                    pop_source,
                )
                tract_records.extend(records)
                county_records.append(county)
            except Exception as error:
                failures.append(f"{geoid}: {error}")
            if number % 50 == 0 or number == len(expected_geoids):
                LOGGER.info(
                    "Processed %d/%d counties; failures=%d",
                    number,
                    len(expected_geoids),
                    len(failures),
                )
    if failures:
        raise SystemExit(
            f"National p0 failed for {len(failures)} counties:\n"
            + "\n".join(failures[:30])
        )

    tract_table = pd.DataFrame(tract_records)
    county_table = pd.DataFrame(county_records)
    eligible = tract_table["population_weighted_mean_ndvi"].notna() & (
        tract_table["ndvi_covered_adult_population"] > 0
    )
    threshold = _weighted_quantile(
        tract_table.loc[eligible, "population_weighted_mean_ndvi"].to_numpy(),
        tract_table.loc[eligible, "ndvi_covered_adult_population"].to_numpy(),
        args.quantile,
    )
    selected = eligible & (
        tract_table["population_weighted_mean_ndvi"] <= threshold
    )
    p0 = float(
        np.average(
            tract_table.loc[selected, "places_depression_prevalence"],
            weights=tract_table.loc[selected, "ndvi_covered_adult_population"],
        )
    )

    import yaml

    model = (yaml.safe_load((BASE_DIR / "config.yaml").read_text()) or {}).get(
        "model", {}
    )
    odds = (
        float(model.get("effect_size_or", 0.931)),
        float(model.get("effect_size_or_low", 0.887)),
        float(model.get("effect_size_or_high", 0.977)),
    )
    rr = tuple(or_to_rr(value, p0) for value in odds)
    method = f"national_urban_lowest_population_weighted_ndvi_quartile_q{args.quantile:g}"
    if not args.no_write_config:
        update_config(p0, rr[0], rr[1], rr[2], odds[0], odds[1], odds[2], method)

    summaries = BASE_DIR / "results/summaries"
    summaries.mkdir(parents=True, exist_ok=True)
    tract_table.to_csv(summaries / "national_p0_tracts.csv", index=False)
    county_table.to_csv(summaries / "national_p0_county_qa.csv", index=False)
    write_report(
        summaries / "national_p0.md",
        p0,
        threshold,
        rr,
        tract_table,
        county_table,
        args.quantile,
    )
    LOGGER.info(
        "Locked p0=%.6f; RR=%.6f (%.6f-%.6f); threshold=%.6f",
        p0,
        rr[0],
        rr[1],
        rr[2],
        threshold,
    )


if __name__ == "__main__":
    main()
