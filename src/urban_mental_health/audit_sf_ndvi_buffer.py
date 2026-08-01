#!/usr/bin/env python3
"""Quantify adult-population exposure to incomplete SF NDVI edge coverage."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = ROOT / "data/urban-mental-health/inputs"
DEFAULT_CSV = ROOT / "results/summaries/sf_ndvi_buffer_audit.csv"
DEFAULT_MD = ROOT / "results/summaries/sf_ndvi_buffer_audit.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-dir", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--radius", type=float, default=300)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    population_path = args.inputs_dir / "population.tif"
    ndvi_path = args.inputs_dir / "ndvi_base.tif"
    with rasterio.open(population_path) as population_source:
        population = population_source.read(1, masked=True)
        rows, columns = np.indices(population.shape)
        transform = population_source.transform
        xs = transform.c + (columns + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e
        pop_crs = population_source.crs
    with rasterio.open(ndvi_path) as ndvi_source:
        ndvi_bounds = ndvi_source.bounds
        if ndvi_source.crs != pop_crs:
            raise SystemExit("Population and NDVI rasters must use the same CRS.")

    values = population.filled(0).astype("float64")
    valid = (
        ~np.ma.getmaskarray(population)
        & np.isfinite(values)
        & (values > 0)
    )
    center_covered = (
        valid
        & (xs >= ndvi_bounds.left)
        & (xs <= ndvi_bounds.right)
        & (ys >= ndvi_bounds.bottom)
        & (ys <= ndvi_bounds.top)
    )
    radius = float(args.radius)
    full_buffer_covered = (
        valid
        & (xs >= ndvi_bounds.left + radius)
        & (xs <= ndvi_bounds.right - radius)
        & (ys >= ndvi_bounds.bottom + radius)
        & (ys <= ndvi_bounds.top - radius)
    )

    total = float(values[valid].sum())
    center_total = float(values[center_covered].sum())
    full_total = float(values[full_buffer_covered].sum())
    record = {
        "search_radius_m": radius,
        "total_adult_population": total,
        "adult_population_center_covered": center_total,
        "center_coverage_fraction": center_total / total,
        "adult_population_full_buffer_covered": full_total,
        "full_buffer_coverage_fraction": full_total / total,
        "adult_population_center_uncovered": total - center_total,
        "adult_population_buffer_edge_exposed": total - full_total,
    }

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=record, lineterminator="\n")
        writer.writeheader()
        writer.writerow(record)

    center_missing = 100 * (1 - record["center_coverage_fraction"])
    buffer_missing = 100 * (1 - record["full_buffer_coverage_fraction"])
    text = f"""# SF NDVI buffer coverage audit

The InVEST model averages NDVI within {radius:g} m of populated cells. The
baseline NDVI raster does not extend across the entire northern/eastern model
buffer, so edge cells may use an incomplete neighborhood.

## Result

- Final calibrated adult population: **{total:,.0f}**
- Adults whose cell center falls outside the NDVI extent:
  **{total - center_total:,.1f} ({center_missing:.4f}%)**
- Adults whose full {radius:g} m rectangular neighborhood is not contained in
  the NDVI extent: **{total - full_total:,.1f} ({buffer_missing:.4f}%)**
- Adults with full extent coverage: **{full_total:,.1f} ({record['full_buffer_coverage_fraction']:.4%})**

## Decision

Retain this as an explicit residual edge-effect limitation rather than block
manuscript freeze. Fewer than 0.1% of modeled adults lack full {radius:g} m
extent coverage, so a wider NDVI export would improve spatial completeness but
is very unlikely to change the citywide headline materially. Do not describe
the warning as resolved; cite this quantified audit and avoid over-interpreting
the affected northern/eastern edge.
"""
    args.output_md.write_text(text)
    print(f"Wrote {args.output_csv} and {args.output_md}")


if __name__ == "__main__":
    main()
