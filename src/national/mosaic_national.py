#!/usr/bin/env python3
"""
Mosaic per-county national model outputs into seamless national layers.

Each county run (data/.../runs/national/<scenario>/<GEOID>/output/) produces
per-pixel rasters (preventable_cases_<GEOID>.tif, preventable_cost_<GEOID>.tif)
and a per-tract summary (preventable_cases_cost_sum_<GEOID>.{csv,gpkg}). This
stitches the 1,000+ counties of one scenario into:

  1. a VRT virtual mosaic per variable         (instant, no data duplication)
  2. a Cloud-Optimized GeoTIFF                 (native 90 m by default, values
                                               unchanged; optional downsample uses
                                               count-preserving '-r sum')
  3. a national per-tract vector mosaic (.gpkg) (for choropleths / joins)
  4. a national totals table (.csv)            (per-county + national sums)

and QA-checks that the raster mosaic sum ~ the sum of per-county CSV totals.

Reusable across scenarios (existing_greenness, uniform_005, best_potential_p95,
radius_500m, ...): just change --scenario.

REQUIREMENTS (conda env `snapp`): GDAL CLI (gdalbuildvrt, gdalwarp), geopandas,
pandas, rasterio, numpy.

USAGE
    python src/national/mosaic_national.py \
        --runs-dir /Users/you/Documents/snapp/SNAPP/data/urban-mental-health/runs/national \
        --scenario existing_greenness
    # single variable, native-res COG:
    python src/national/mosaic_national.py --scenario uniform_005 --var cases --resolution 30
"""

import argparse
import csv
import glob
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("mosaic_national")

VARS = {"cases": "preventable_cases", "cost": "preventable_cost"}
MIN_TIF_BYTES = 1024                       # guard against empty/partial tifs


def require_gdal():
    for tool in ("gdalbuildvrt", "gdalwarp", "gdal_translate"):
        if shutil.which(tool) is None:
            sys.exit(f"'{tool}' not found. Install GDAL in the env (conda install -c conda-forge gdal).")


def discover(scen_dir: Path, prefix: str) -> list:
    """Valid per-county rasters for one variable (skips empty/unreadable)."""
    tifs = sorted(glob.glob(str(scen_dir / "*" / "output" / f"{prefix}_*.tif")))
    good = [t for t in tifs if Path(t).stat().st_size >= MIN_TIF_BYTES]
    LOGGER.info("%s: %d county rasters (%d skipped as empty)",
                prefix, len(good), len(tifs) - len(good))
    return good


def preflight(tifs: list):
    """Report CRS/res/nodata; return (crs, res, nodata) of the first, flag mismatches."""
    import rasterio
    from collections import Counter
    crs0 = res0 = nodata0 = None
    mismatches = 0
    res_counts, crs_counts = Counter(), Counter()
    for i, t in enumerate(tifs):
        try:
            with rasterio.open(t) as d:
                crs, res, nd = str(d.crs), tuple(round(x, 3) for x in d.res), d.nodata
        except Exception as e:
            LOGGER.warning("unreadable: %s (%s)", t, e); mismatches += 1; continue
        res_counts[abs(res[0])] += 1
        crs_counts[crs] += 1
        if i == 0:
            crs0, res0, nodata0 = crs, res, nd
            LOGGER.info("reference: CRS=%s res=%s nodata=%s", crs0, res0, nodata0)
        elif crs != crs0 or res != res0:
            mismatches += 1
            if mismatches <= 5:
                LOGGER.warning("mismatch in %s: CRS=%s res=%s", Path(t).name, crs, res)
    # Report the resolution spread so grid drift is visible.
    top_res = ", ".join(f"{r}m x{n}" for r, n in res_counts.most_common(5))
    LOGGER.info("source x-resolutions (top): %s", top_res)
    if len(crs_counts) > 1:
        LOGGER.warning("MIXED CRS across tiles: %s — reproject first, or mosaic per CRS.",
                       dict(crs_counts))
    if mismatches:
        LOGGER.warning("%d rasters differ in CRS/res from the reference — they'll be "
                       "re-gridded to the modal resolution with count-preserving -r sum.",
                       mismatches)
    modal_res = res_counts.most_common(1)[0][0] if res_counts else (abs(res0[0]) if res0 else None)
    return crs0, res0, nodata0, modal_res


def standardize_to_grid(tifs: list, target_res: float, tmp_dir: Path, nodata) -> list:
    """Return a tile list all at target_res. Tiles already at target_res pass
    through unchanged; off-grid tiles (e.g. 30 m among 90 m) are re-gridded with
    '-r sum' so per-pixel COUNTS are conserved (nearest would drop 8/9 of a
    30 m->90 m cell). Only the non-conforming tiles are warped."""
    import rasterio
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out, n_fixed = [], 0
    for t in tifs:
        try:
            with rasterio.open(t) as d:
                rx = abs(d.res[0])
        except Exception:
            out.append(t); continue
        if abs(rx - target_res) <= 0.5:
            out.append(t)                                  # already on grid
        else:
            dst = tmp_dir / Path(t).name
            cmd = ["gdalwarp", "-overwrite", "-r", "sum",
                   "-tr", str(target_res), str(target_res)]
            if nodata is not None:
                cmd += ["-srcnodata", str(nodata), "-dstnodata", str(nodata)]
            cmd += ["-of", "GTiff", "-co", "COMPRESS=DEFLATE", t, str(dst)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            out.append(str(dst)); n_fixed += 1
    LOGGER.info("standardized %d off-grid tiles to %g m with -r sum (counts conserved); "
                "%d already on grid", n_fixed, target_res, len(out) - n_fixed)
    return out


def build_vrt(tifs: list, out_vrt: Path, nodata, source_res=None):
    """gdalbuildvrt over a file list (avoids arg-length limits at 1,000+ files).

    Resolution rule (NEVER the default 'average', which drifts the grid off the
    native size when tiles aren't byte-identical):
      - source_res given  -> pin the mosaic grid to that size (-resolution user
        -tr r r); already-90 m tiles pass through unchanged, stray tiles snap to it.
      - else              -> '-resolution highest' (finest native tile; no
        averaging-down).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(tifs)); listfile = fh.name
    cmd = ["gdalbuildvrt"]
    if source_res is not None:
        cmd += ["-resolution", "user", "-tr", str(source_res), str(source_res)]
    else:
        cmd += ["-resolution", "highest"]
    if nodata is not None:
        cmd += ["-srcnodata", str(nodata), "-vrtnodata", str(nodata)]
    cmd += ["-input_file_list", listfile, str(out_vrt)]
    subprocess.run(cmd, check=True)
    Path(listfile).unlink(missing_ok=True)
    LOGGER.info("Wrote %s (%s)", out_vrt,
                f"pinned {source_res} m" if source_res else "resolution=highest")


def to_cog(vrt: Path, out_cog: Path):
    """Materialize a COG from the VRT at its native grid, values unchanged.

    The count-preserving work (re-gridding mixed 30/90 m tiles with -r sum) is done
    upstream by standardize_to_grid, so the VRT is already uniform and correct here —
    a straight translate keeps exact pixel values."""
    cmd = ["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE",
           "-co", "OVERVIEW_RESAMPLING=AVERAGE", "-co", "BIGTIFF=IF_SAFER",
           str(vrt), str(out_cog)]
    subprocess.run(cmd, check=True)
    LOGGER.info("Wrote %s (native grid, values unchanged)", out_cog)


def raster_sum(path: Path) -> float:
    import numpy as np, rasterio
    with rasterio.open(path) as d:
        a = d.read(1, masked=True)
    return float(np.nansum(a.filled(0.0)))


def vector_mosaic(scen_dir: Path, out_gpkg: Path, scenario: str):
    import geopandas as gpd, pandas as pd
    gpkgs = sorted(glob.glob(str(scen_dir / "*" / "output" / "*sum*.gpkg")))
    parts = []
    for g in gpkgs:
        try:
            gdf = gpd.read_file(g)
            gdf["src_geoid"] = Path(g).stem.split("_")[-1]
            parts.append(gdf)
        except Exception as e:
            LOGGER.warning("skip vector %s (%s)", Path(g).name, e)
    if not parts:
        LOGGER.warning("no summary gpkgs found; skipping vector mosaic."); return None
    nat = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)
    nat["scenario"] = scenario
    nat.to_file(out_gpkg, driver="GPKG")
    LOGGER.info("Wrote %s (%d tract features)", out_gpkg, len(nat))
    return nat


def totals_csv(scen_dir: Path, out_csv: Path) -> float:
    """Per-county ALL-row totals -> national CSV; returns the national case total."""
    rows, nat_cases, nat_cost = [], 0.0, 0.0
    for c in sorted(csvf for csvf in glob.glob(str(scen_dir / "*" / "output" / "*sum*.csv"))):
        geoid = Path(c).stem.split("_")[-1]
        tc = tcost = None
        for r in csv.DictReader(open(c)):
            if str(r.get("FID", "")).upper() == "ALL":
                tc = float(r["total_cases"]) if r.get("total_cases") else None
                tcost = float(r["total_cost"]) if r.get("total_cost") else None
        rows.append([geoid, tc if tc is not None else "", tcost if tcost is not None else ""])
        nat_cases += tc or 0.0
        nat_cost += tcost or 0.0
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["GEOID", "preventable_cases", "preventable_cost_usd"])
        w.writerows(rows)
        w.writerow(["NATIONAL", round(nat_cases, 1), round(nat_cost)])
    LOGGER.info("Wrote %s | national: %.0f cases, $%.0f", out_csv, nat_cases, nat_cost)
    return nat_cases


def main():
    ap = argparse.ArgumentParser(description="Mosaic per-county national outputs.")
    ap.add_argument("--runs-dir", type=Path, required=True,
                    help="Path to runs/national (holds the scenario subfolders).")
    ap.add_argument("--scenario", default="existing_greenness")
    ap.add_argument("--var", choices=["cases", "cost", "both"], default="both")
    ap.add_argument("--source-res", type=float, default=None,
                    help="Pin the mosaic grid to this resolution in metres (e.g. 90), "
                         "overriding the auto-picked modal native resolution. Off-grid "
                         "tiles are re-gridded with count-preserving -r sum.")
    ap.add_argument("--resolution", type=float, default=None,
                    help="Downsample the COG to this resolution in metres (count-"
                         "preserving -r sum). Default: keep native (no resampling).")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Output dir (default: <runs-dir>/_mosaics/<scenario>).")
    ap.add_argument("--no-cog", action="store_true", help="VRT only; skip the materialized COG.")
    ap.add_argument("--no-vector", action="store_true", help="Skip the tract .gpkg mosaic.")
    cli = ap.parse_args()

    require_gdal()
    scen_dir = cli.runs_dir / cli.scenario
    if not scen_dir.is_dir():
        sys.exit(f"Scenario dir not found: {scen_dir}")
    out_dir = cli.out_dir or (cli.runs_dir / "_mosaics" / cli.scenario)
    out_dir.mkdir(parents=True, exist_ok=True)

    variables = ["cases", "cost"] if cli.var == "both" else [cli.var]
    for var in variables:
        prefix = VARS[var]
        tifs = discover(scen_dir, prefix)
        if not tifs:
            LOGGER.warning("no rasters for '%s'; skipping.", var); continue
        _, res, nodata, modal_res = preflight(tifs)
        # Target grid: explicit --resolution, else pinned --source-res, else the
        # MODAL native resolution (e.g. 90 m when 872 tiles are 90 m, 295 are 30 m).
        target_res = cli.resolution or cli.source_res or modal_res or (res[0] if res else 90.0)
        # Re-grid every off-target tile with count-preserving -r sum FIRST, so the
        # mosaic is correct for both variables even with the 30/90 m mix. Tiles
        # already at target pass through untouched.
        tifs = standardize_to_grid(tifs, target_res, out_dir / "_standardized" / var, nodata)
        vrt = out_dir / f"national_{cli.scenario}_{var}.vrt"
        build_vrt(tifs, vrt, nodata, source_res=target_res)
        if not cli.no_cog:
            cog = out_dir / f"national_{cli.scenario}_{var}_{int(round(target_res))}m.tif"
            to_cog(vrt, cog)
            # QA: mosaic sum vs per-county CSV totals (cases only)
            if var == "cases":
                nat_from_csv = totals_csv(scen_dir, out_dir / f"national_{cli.scenario}_totals.csv")
                nat_from_cog = raster_sum(cog)
                diff = 100 * abs(nat_from_cog - nat_from_csv) / nat_from_csv if nat_from_csv else float("nan")
                flag = "OK" if diff < 2 else "CHECK (buffer overlap or resampling)"
                LOGGER.info("QA cases: COG sum=%.0f vs CSV sum=%.0f (%.1f%% diff) -> %s",
                            nat_from_cog, nat_from_csv, diff, flag)
        elif var == "cases":
            totals_csv(scen_dir, out_dir / f"national_{cli.scenario}_totals.csv")

    if not cli.no_vector:
        vector_mosaic(scen_dir, out_dir / f"national_{cli.scenario}_tracts.gpkg", cli.scenario)

    LOGGER.info("Done -> %s", out_dir)


if __name__ == "__main__":
    main()
