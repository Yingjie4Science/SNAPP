#!/usr/bin/env python3
"""Advanced distributional equity analysis for the urban mental-health HIA.

This module extends the basic concentration-curve screen into a reproducible
distributional health-impact assessment.  It reports relative inequality (CI),
absolute inequality (SII), bootstrap intervals, spatial clustering, and a
transparent tract-level priority score used by the matched-budget allocation
scenarios.

The script intentionally distinguishes *social vulnerability* from observed
displacement.  Renter share is used only as an implementation-safeguard flag,
not as evidence that greening causes gentrification.
"""

import argparse
import csv
import glob
import logging
import os
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("advanced_equity")

BASE_DIR = Path(__file__).resolve().parents[2]
UMH = BASE_DIR / "data" / "urban-mental-health"
INPUTS = UMH / "inputs"
RUNS = UMH / "runs" / "sf_scenarios"
RESULTS = BASE_DIR / "results"
OUT_SUMMARY = RESULTS / "summaries" / "advanced_equity_summary.md"
OUT_METRICS = RESULTS / "summaries" / "advanced_equity_metrics.csv"
OUT_TRACTS = RESULTS / "summaries" / "advanced_equity_tracts.csv"
OUT_PRIORITY = RESULTS / "summaries" / "advanced_equity_priority_tracts.csv"
FIG_INTERVALS = RESULTS / "figures" / "equity_svi_inequality_intervals.png"
FIG_PRIORITY = RESULTS / "figures" / "equity_priority_map.png"
FIG_LISA = RESULTS / "figures" / "equity_priority_clusters.png"
FIG_PARETO = RESULTS / "figures" / "equity_health_pareto.png"
SVI_URL = ("https://onemap.cdc.gov/onemapservices/rest/services/SVI/"
           "CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2/query")

ACS_VARS = {
    "acs_population": "B01003_001E",
    "median_income": "B19013_001E",
    "households": "B19001_001E",
    "low_income_households": ("B19001_002E", "B19001_003E", "B19001_004E", "B19001_005E"),
    "high_income_households": ("B19001_016E", "B19001_017E"),
    "occupied_households": "B25003_001E",
    "renter_households": "B25003_003E",
    "race_total": "B03002_001E",
    "nonhisp_white": "B03002_003E",
}


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path.home() / ".config" / "snapp" / ".env")
    except ImportError:
        pass


def fetch_acs(state: str, county: str, year: int, key: str | None) -> dict:
    """Fetch required ACS values by tract, preserving leading-zero GEOIDs."""
    import requests
    fields = [v for v in ACS_VARS.values() if isinstance(v, str)]
    fields += [v for pair in ACS_VARS.values() if isinstance(pair, tuple) for v in pair]
    url = (f"https://api.census.gov/data/{year}/acs/acs5?get=" + ",".join(fields) +
           f"&for=tract:*&in=state:{state}%20county:{county}")
    response = requests.get(url, params={"key": key} if key else None, timeout=120)
    if response.status_code != 200 or not response.text.lstrip().startswith("["):
        sys.exit(f"ACS request failed (HTTP {response.status_code}): {response.text[:300]}")
    rows = response.json()
    index = {name: i for i, name in enumerate(rows[0])}
    out = {}
    for row in rows[1:]:
        geoid = row[index["state"]] + row[index["county"]] + row[index["tract"]]
        values = {}
        for label, source in ACS_VARS.items():
            try:
                if isinstance(source, tuple):
                    values[label] = sum(float(row[index[v]]) for v in source)
                else:
                    values[label] = float(row[index[source]])
            except (KeyError, TypeError, ValueError):
                values[label] = np.nan
        out[geoid] = values
    return out


def fetch_svi(state: str, county: str) -> dict:
    """Fetch official 2022 CDC/ATSDR tract-level overall SVI percentile."""
    import requests
    params = {"where": f"ST='{state}' AND STCNTY='{state}{county}'",
              "outFields": "FIPS,RPL_THEMES", "returnGeometry": "false", "f": "json"}
    response = requests.get(SVI_URL, params=params, timeout=120)
    data = response.json()
    if response.status_code != 200 or data.get("error"):
        sys.exit(f"CDC SVI request failed: {data.get('error', response.text[:300])}")
    return {str(f["attributes"]["FIPS"]).zfill(11): float(f["attributes"]["RPL_THEMES"])
            for f in data.get("features", [])
            if f.get("attributes", {}).get("RPL_THEMES") not in (None, -999)}


def load_scenario_gdf(label: str):
    import geopandas as gpd
    matches = sorted(glob.glob(str(RUNS / label / "output" / "*sum*.gpkg")))
    if not matches:
        return None
    gdf = gpd.read_file(matches[0])[["GEOID", "sum_cases", "sum_cost", "geometry"]].copy()
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    return gdf


def adult_population_by_tract(gdf):
    """Aggregate the model's adult-scaled population raster to tract polygons."""
    import rioxarray  # noqa: F401
    from rasterio.features import rasterize
    pop = rioxarray.open_rasterio(INPUTS / "population.tif", masked=True).squeeze()
    work = gdf[["GEOID", "geometry"]].to_crs(pop.rio.crs).reset_index(drop=True)
    transform, shape = pop.rio.transform(), (pop.rio.height, pop.rio.width)
    ids = rasterize(((geom, i + 1) for i, geom in enumerate(work.geometry)),
                    out_shape=shape, transform=transform, fill=0, dtype="int32")
    values = np.asarray(pop.values, dtype=float).ravel()
    flat_ids = ids.ravel()
    valid = np.isfinite(values) & (values > 0) & (flat_ids > 0)
    totals = np.bincount(flat_ids[valid], weights=values[valid], minlength=len(work) + 1)[1:]
    return dict(zip(work["GEOID"], totals))


def tract_mean_ndvi(gdf):
    """Population-independent baseline greenness diagnostic used for prioritization."""
    import rioxarray  # noqa: F401
    from rasterio.features import rasterize
    ndvi = rioxarray.open_rasterio(INPUTS / "ndvi_base.tif", masked=True).squeeze()
    work = gdf[["GEOID", "geometry"]].to_crs(ndvi.rio.crs).reset_index(drop=True)
    ids = rasterize(((geom, i + 1) for i, geom in enumerate(work.geometry)),
                    out_shape=(ndvi.rio.height, ndvi.rio.width), transform=ndvi.rio.transform(),
                    fill=0, dtype="int32")
    values, flat_ids = np.asarray(ndvi.values, dtype=float).ravel(), ids.ravel()
    valid = np.isfinite(values) & (flat_ids > 0)
    sums = np.bincount(flat_ids[valid], weights=values[valid], minlength=len(work) + 1)[1:]
    counts = np.bincount(flat_ids[valid], minlength=len(work) + 1)[1:]
    return dict(zip(work["GEOID"], np.divide(sums, counts, out=np.full(len(sums), np.nan), where=counts > 0)))


def feasible_increment_by_tract(gdf, target=0.65, delta=0.15):
    """Maximum LULC-feasible NDVI increment by tract for comparable allocation efficiency."""
    import rioxarray  # noqa: F401
    from rasterio.features import rasterize
    ndvi = rioxarray.open_rasterio(INPUTS / "ndvi_base.tif", masked=True).squeeze()
    lulc = rioxarray.open_rasterio(UMH / "raw" / "nlcd" / "nlcd_landcover.tif", masked=True).squeeze()
    lulc = lulc.rio.reproject_match(ndvi, resampling=0)
    work = gdf[["GEOID", "geometry"]].to_crs(ndvi.rio.crs).reset_index(drop=True)
    ids = rasterize(((geom, i + 1) for i, geom in enumerate(work.geometry)),
                    out_shape=(ndvi.rio.height, ndvi.rio.width), transform=ndvi.rio.transform(),
                    fill=0, dtype="int32")
    base, land = np.asarray(ndvi.values, dtype=float), np.asarray(lulc.values)
    eligible = np.isin(land, [21, 22, 31]) & np.isfinite(base) & (ids > 0)
    potential = np.where(eligible, np.maximum(0, np.minimum(base + delta, target) - base), 0)
    sums = np.bincount(ids.ravel(), weights=potential.ravel(), minlength=len(work) + 1)[1:]
    return dict(zip(work["GEOID"], sums))


def weighted_rank(x, w):
    order = np.argsort(x)
    ws = w[order] / w.sum()
    out = np.empty_like(ws)
    out[order] = np.cumsum(ws) - ws / 2
    return out


def concentration_index(y, w, rankvar):
    r = weighted_rank(rankvar, w)
    mu = np.average(y, weights=w)
    return float(2 * np.average((y - mu) * (r - 0.5), weights=w) / mu) if mu else np.nan


def slope_index(y, w, rankvar):
    """Population-weighted SII: rate difference per 1,000 from rank 0 to 1."""
    r = weighted_rank(rankvar, w)
    X = np.column_stack([np.ones(len(r)), r])
    root_w = np.sqrt(w / w.mean())
    beta = np.linalg.lstsq(X * root_w[:, None], y * root_w, rcond=None)[0]
    return float(beta[1] * 1000)


def bootstrap(y, w, rank, n, rng):
    ci, sii = [], []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        ci.append(concentration_index(y[idx], w[idx], rank[idx]))
        sii.append(slope_index(y[idx], w[idx], rank[idx]))
    return (np.nanpercentile(ci, [2.5, 97.5]), np.nanpercentile(sii, [2.5, 97.5]))


def knn_weights(coords, k=6):
    d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    return np.argsort(d, axis=1)[:, :min(k, len(coords) - 1)]


def moran_lisa(values, coords, permutations, rng):
    """Global Moran's I and a conservative permutation-significant local cluster class."""
    z = (values - values.mean()) / values.std(ddof=0)
    nbr = knn_weights(coords)
    lag = z[nbr].mean(axis=1)
    global_i = float((z * lag).sum() / (z * z).sum())
    local = z * lag
    perm = np.empty((permutations, len(values)))
    for i in range(permutations):
        zp = rng.permutation(z)
        perm[i] = z * zp[nbr].mean(axis=1)
    p = (np.sum(np.abs(perm) >= np.abs(local), axis=0) + 1) / (permutations + 1)
    cluster = np.full(len(values), "not significant", dtype=object)
    cluster[(p < 0.05) & (z >= 0) & (lag >= 0)] = "high-high priority"
    cluster[(p < 0.05) & (z < 0) & (lag < 0)] = "low-low priority"
    cluster[(p < 0.05) & (z >= 0) & (lag < 0)] = "high-low outlier"
    cluster[(p < 0.05) & (z < 0) & (lag >= 0)] = "low-high outlier"
    return global_i, local, p, cluster


def classify(ci, measure):
    if abs(ci) <= 0.02:
        return "no material gradient"
    privileged = measure in {"income", "ice_income"}
    if privileged:
        return "equity-promoting" if ci < 0 else "advantage-concentrating"
    return "equity-promoting" if ci > 0 else "vulnerability-under-serving"


def write_outputs(base, scenarios, bootstrap_n, permutations):
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    load_env()
    key = os.environ.get("CENSUS_API_KEY")
    acs = fetch_acs("06", "075", 2023, key)
    svi = fetch_svi("06", "075")
    adult_pop = adult_population_by_tract(base)
    mean_ndvi = tract_mean_ndvi(base)
    feasible_increment = feasible_increment_by_tract(base)
    work = base[["GEOID", "geometry"]].copy()
    work["adult_population"] = work.GEOID.map(adult_pop)
    work["baseline_ndvi"] = work.GEOID.map(mean_ndvi)
    work["feasible_increment"] = work.GEOID.map(feasible_increment)
    for name in ("median_income", "acs_population", "households", "low_income_households",
                 "high_income_households", "occupied_households", "renter_households",
                 "race_total", "nonhisp_white"):
        work[name] = work.GEOID.map(lambda g: acs.get(g, {}).get(name, np.nan))
    work["svi"] = work.GEOID.map(svi)
    work["ice_income"] = (work.high_income_households - work.low_income_households) / work.households
    work["renter_share"] = work.renter_households / work.occupied_households
    work["minority_share"] = 1 - work.nonhisp_white / work.race_total
    work = work.replace([np.inf, -np.inf], np.nan)
    covariates = work.copy()
    uniform_work = None
    rng = np.random.default_rng(20260713)
    metrics = []
    measure_defs = [("income", "median_income", "higher = more advantaged"),
                    ("svi", "svi", "higher = more vulnerable"),
                    ("ice_income", "ice_income", "higher = more privileged"),
                    ("renter_share", "renter_share", "higher = implementation-safeguard vulnerability"),
                    ("minority_share", "minority_share", "higher = historically underserved population share")]
    for label, gdf in scenarios.items():
        data = gdf[["GEOID", "sum_cases"]].rename(columns={"sum_cases": "cases"})
        d = covariates.merge(data, on="GEOID", how="inner")
        d["rate"] = d.cases / d.adult_population
        for measure, col, direction in measure_defs:
            x = d[["rate", "adult_population", col]].dropna()
            if len(x) < 20:
                continue
            y, weights, rank = x.rate.to_numpy(), x.adult_population.to_numpy(), x[col].to_numpy()
            ci, sii = concentration_index(y, weights, rank), slope_index(y, weights, rank)
            ci_int, sii_int = bootstrap(y, weights, rank, bootstrap_n, rng)
            metrics.append({"scenario": label, "measure": measure, "rank_direction": direction,
                            "matched_tracts": len(x), "concentration_index": ci,
                            "ci_low": ci_int[0], "ci_high": ci_int[1], "sii_per_1000": sii,
                            "sii_low": sii_int[0], "sii_high": sii_int[1],
                            "interpretation": classify(ci, measure)})
        if label == "uniform_005":
            uniform_work = d.copy()

    if uniform_work is None:
        sys.exit("uniform_005 metrics could not be joined to tract covariates.")
    work = uniform_work

    # Priority score: equal-weight need (benefit efficiency), vulnerability, and greenness deficit.
    work["health_efficiency"] = work.cases / work.feasible_increment
    work["health_efficiency"] = work.health_efficiency.replace([np.inf, -np.inf], np.nan)
    for col in ("health_efficiency", "svi", "baseline_ndvi", "renter_share"):
        lo, hi = work[col].quantile([0.05, 0.95])
        work[f"z_{col}"] = ((work[col].clip(lo, hi) - lo) / (hi - lo)).clip(0, 1)
    work["health_score"] = work.z_health_efficiency
    work["equity_score"] = (0.5 * work.z_health_efficiency + 0.35 * work.z_svi +
                            0.15 * (1 - work.z_baseline_ndvi))
    work["balanced_score"] = 0.5 * work.health_score + 0.5 * work.equity_score
    work["safeguard_flag"] = ((work.z_svi >= 0.75) & (work.z_renter_share >= 0.75)).astype(int)
    centroids = work.to_crs("EPSG:26910").geometry.centroid
    coords = np.column_stack([centroids.x, centroids.y])
    ranked = work.equity_score.notna().to_numpy()
    moran_i, local_i, lisa_p, cluster = moran_lisa(work.loc[ranked, "equity_score"].to_numpy(),
                                                    coords[ranked], permutations, rng)
    work["local_moran_i"] = np.nan
    work["lisa_p"] = np.nan
    work["priority_cluster"] = "not ranked (missing SVI or zero feasible capacity)"
    work.loc[ranked, "local_moran_i"] = local_i
    work.loc[ranked, "lisa_p"] = lisa_p
    work.loc[ranked, "priority_cluster"] = cluster
    priority_rank = work.equity_score.rank(method="first", pct=True)
    work["priority_decile"] = np.where(priority_rank.notna(),
                                        np.minimum(np.ceil(priority_rank * 10), 10), np.nan)

    RESULTS.joinpath("summaries").mkdir(parents=True, exist_ok=True)
    with open(OUT_METRICS, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(metrics[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(metrics)
    tract_cols = [c for c in work.columns if c != "geometry"]
    work[tract_cols].to_csv(OUT_TRACTS, index=False)
    work[work.priority_decile >= 8][tract_cols].to_csv(OUT_PRIORITY, index=False)

    # Publication-style interval plot: SVI relative and absolute inequality by scenario.
    primary = [m for m in metrics if m["measure"] == "svi"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    labels = [m["scenario"].replace("_", " ") for m in primary]
    yy = np.arange(len(primary))
    for ax, point, lo, hi, title, zero in [
        (axes[0], "concentration_index", "ci_low", "ci_high", "Relative inequality: SVI concentration index", 0),
        (axes[1], "sii_per_1000", "sii_low", "sii_high", "Absolute inequality: SII", 0),
    ]:
        val = np.array([m[point] for m in primary]); low = np.array([m[lo] for m in primary]); high = np.array([m[hi] for m in primary])
        ax.errorbar(val, yy, xerr=np.vstack([val-low, high-val]), fmt="o", color="#d95f02", capsize=3)
        ax.axvline(zero, color="0.5", lw=1, ls="--")
        ax.set_title(title); ax.set_xlabel("equity-favoring →" if point == "concentration_index" else "cases / 1,000 adults")
        ax.grid(axis="x", alpha=.2)
    axes[0].set_yticks(yy, labels); axes[0].invert_yaxis()
    fig.suptitle("SVI distribution of modeled greening benefit (95% bootstrap intervals)", y=1.02)
    FIG_INTERVALS.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_INTERVALS, dpi=220, bbox_inches="tight"); plt.close(fig)

    # Health-equity frontier: higher SVI CI means more benefit reaches vulnerable tracts.
    totals = {label: float(gdf["sum_cases"].sum()) for label, gdf in scenarios.items()}
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    label_offsets = {
        "uniform_005": (4, 5), "greenable_005": (4, 12), "lulc_masked": (4, 5),
        "canopy_30pct": (4, 5), "best_potential_p95": (4, 5),
        "health_priority_feasible": (4, 5), "equity_priority_feasible": (4, 5),
        "balanced_priority_feasible": (4, 5),
    }
    for m in primary:
        x, y = totals.get(m["scenario"], np.nan), m["concentration_index"]
        color = "#d95f02" if "equity_priority" in m["scenario"] else "#2c7fb8"
        marker = "s" if "balanced" in m["scenario"] else "o"
        ax.scatter(x, y, s=55, color=color, marker=marker, edgecolor="white", zorder=3)
        ax.annotate(m["scenario"].replace("_", " "), (x, y), xytext=label_offsets.get(m["scenario"], (4, 4)),
                    textcoords="offset points", fontsize=7)
    ax.axhline(0, color="0.5", lw=1, ls="--")
    ax.set_xlabel("Total preventable depression cases / year")
    ax.set_ylabel("SVI concentration index (higher = more vulnerable benefit)")
    ax.set_title("Health–equity trade-off across scenarios")
    ax.grid(alpha=.2)
    fig.savefig(FIG_PARETO, dpi=220, bbox_inches="tight"); plt.close(fig)

    for path, column, title, cmap in [(FIG_PRIORITY, "equity_score", "Equity-priority score for feasible greening", "YlOrRd"),
                                       (FIG_LISA, "priority_cluster", "Spatial clusters of equity-priority score", "Set1")]:
        fig, ax = plt.subplots(figsize=(6, 6))
        legend_kwds = {"loc": "lower left", "fontsize": 7} if column == "priority_cluster" else {"shrink": .65}
        work.plot(column=column, ax=ax, cmap=cmap, legend=True, edgecolor="white", linewidth=.15,
                  legend_kwds=legend_kwds)
        ax.set_axis_off(); ax.set_title(title)
        fig.savefig(path, dpi=220, bbox_inches="tight"); plt.close(fig)

    primary_metrics = [m for m in metrics if m["scenario"] == "uniform_005" and m["measure"] in {"income", "svi", "ice_income"}]
    lines = ["# Advanced equity analysis", "",
             "## Decision finding", "",
             "The analysis compares relative (concentration index) and absolute (slope index of inequality) "
             "distributions of modeled preventable depression rates, with 95% tract-bootstrap intervals. "
             "It also identifies spatially clustered priority tracts and supplies transparent scores for "
             "matched-budget health, equity, and balanced allocation scenarios.", "",
             "## Primary distributional results: uniform +0.05 reference", "",
             "| Equity lens | CI (95% CI) | SII cases / 1,000 adults (95% CI) | Interpretation |",
             "|---|---:|---:|---|"]
    for m in primary_metrics:
        lines.append(f"| {m['measure']} | {m['concentration_index']:+.3f} ({m['ci_low']:+.3f}, {m['ci_high']:+.3f}) | "
                     f"{m['sii_per_1000']:+.2f} ({m['sii_low']:+.2f}, {m['sii_high']:+.2f}) | {m['interpretation']} |")
    lines += ["", f"Global Moran's I for the equity-priority score: **{moran_i:+.3f}** (k-nearest-neighbor diagnostic). "
              "Priority clusters are planning targets, not causal estimates.", "",
              f"![SVI inequality intervals](../figures/{FIG_INTERVALS.name})",
              "<sub>Relative and absolute SVI inequality by scenario; error bars are 95% tract-bootstrap intervals.</sub>", "",
              f"![Equity-priority map](../figures/{FIG_PRIORITY.name})",
              "<sub>Higher scores combine modeled cases per feasible NDVI increment, SVI, and low baseline greenness.</sub>", "",
              f"![Health–equity trade-off](../figures/{FIG_PARETO.name})",
              "<sub>Each point is a modeled scenario; vertical position indicates whether benefit is concentrated in higher-SVI tracts.</sub>", "",
              f"![Equity-priority spatial clusters](../figures/{FIG_LISA.name})",
              "<sub>Local spatial clusters of the equity-priority score; use as a screening map for place-based planning, not a causal inference map.</sub>", "",
              "## Methods and limits", "",
              "Income and ICE rank privilege upward; SVI, renter share, and minority share rank potential vulnerability upward. "
              "The SII is a population-weighted linear difference from the bottom to the top of a fractional rank. "
              "Bootstrap intervals reflect tract-sampling uncertainty only; they do not replace epidemiologic effect-size uncertainty. "
              f"{int(work.svi.isna().sum())} tracts without valid SVI were excluded from SVI-ranked and equity-allocation scoring rather than imputed; "
              f"{int((work.feasible_increment <= 0).sum())} additional tracts had no feasible NDVI capacity and therefore received no allocation score. "
              "The renter/SVI safeguard flag is not a measure of observed displacement and should trigger community co-design and anti-displacement review."]
    OUT_SUMMARY.write_text("\n".join(lines) + "\n")
    LOGGER.info("Wrote advanced equity outputs: %s", OUT_SUMMARY)
    return work, metrics


def main():
    ap = argparse.ArgumentParser(description="Advanced distributional equity analysis.")
    ap.add_argument("--bootstrap", type=int, default=400, help="Tract-bootstrap draws per metric.")
    ap.add_argument("--permutations", type=int, default=499, help="Spatial permutation draws.")
    ap.add_argument("--scenario", action="append", help="Scenario label to include; repeatable.")
    cli = ap.parse_args()
    labels = cli.scenario or ["uniform_005", "greenable_005", "lulc_masked", "canopy_30pct",
                              "best_potential_p95", "health_priority_feasible",
                              "equity_priority_feasible", "balanced_priority_feasible"]
    scenarios = {label: load_scenario_gdf(label) for label in labels}
    scenarios = {label: gdf for label, gdf in scenarios.items() if gdf is not None}
    if "uniform_005" not in scenarios:
        sys.exit("uniform_005 scenario output is required; run run_scenarios.py first.")
    base = scenarios["uniform_005"]
    write_outputs(base, scenarios, cli.bootstrap, cli.permutations)


if __name__ == "__main__":
    main()
