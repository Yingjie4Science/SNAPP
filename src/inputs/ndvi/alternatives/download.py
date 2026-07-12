#!/usr/bin/env python3
"""
Download 2024 Copernicus NDVI 300m (v2.0) global 10-daily files from the
Copernicus Data Space Ecosystem (CDSE) via its OData API, then clip each
file to a San Francisco bounding box and save the small subsets locally.

WHY THIS SHAPE:
- CDSE OData does NOT support server-side spatial subsetting, so this script
  downloads each *global* 10-daily NetCDF file (36 "dekads" for 2024, each a
  few hundred MB) and clips it locally with xarray. Expect ~10-15 GB of
  temporary downloads. The clipped SF outputs are tiny (a few KB each).
- If you only care about San Francisco and want to avoid the big downloads,
  the Sentinel Hub Process API (also on CDSE) can return just the SF window
  server-side. Ask and I'll write that version instead.

CREDENTIALS:
    Copy .env.example to .env and fill in your CDSE username/password.
    The .env file is gitignored and never committed.

REQUIREMENTS:
    pip install -r requirements.txt

USAGE:
    python download_sf_ndvi_2024.py

Register a free CDSE account: https://dataspace.copernicus.eu  (see README).
"""

import os
import sys
import time
from pathlib import Path

import requests

try:
    import xarray as xr
except ImportError:
    xr = None  # only needed for the clipping step

# Load credentials from a local .env file if python-dotenv is installed.
# Falls back silently to real environment variables if it isn't.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
except ImportError:
    pass

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
YEAR = 2024

# San Francisco bounding box (WGS84 lon/lat). Covers the SF peninsula city.
# Widen if you want the whole Bay Area.
SF_BBOX = {
    "lon_min": -122.55,
    "lon_max": -122.35,
    "lat_min": 37.70,
    "lat_max": 37.83,
}

# NDVI 300m product to target. "V2" = the v2.0 product you linked (2020-2025).
# Switch to "V3" for the current version (2014-present) if you prefer.
PRODUCT_VERSION = "V2"

# Output locations. This script lives in <project>/src/inputs/ndvi/, and the whole
# data/ tree is kept out of git via .gitignore.
BASE_DIR = Path(__file__).resolve().parents[4]      # project root (SNAPP)
DATASET_DIR = BASE_DIR / "data" / "sf-ndvi-2024"
RAW_DIR = DATASET_DIR / "raw"           # full global downloads (large, temporary)
OUT_DIR = DATASET_DIR / "processed"     # clipped SF outputs land here
KEEP_GLOBAL_FILES = False               # set True to keep the big raw files

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
def get_access_token(username: str, password: str) -> str:
    """Exchange CDSE username/password for an OAuth access token."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=60,
    )
    if resp.status_code == 401:
        # CDSE explains *why* in the body — surface it instead of a bare 401.
        try:
            err = resp.json()
            reason = err.get("error_description") or err.get("error") or resp.text
        except ValueError:
            reason = resp.text
        sys.exit(
            "CDSE rejected your login (HTTP 401).\n"
            f"  Reason: {reason}\n"
            f"  Username used: {username}\n"
            "Fixes:\n"
            "  - Confirm you can log in at https://dataspace.copernicus.eu with this\n"
            "    exact email + password in a browser.\n"
            "  - Make sure the account email is verified/activated.\n"
            "  - If you rotated the password, update CDSE_PASSWORD in .env.\n"
            "  - If you enabled two-factor auth (TOTP), the password grant won't\n"
            "    work; disable it or use a token-based flow."
        )
    resp.raise_for_status()
    return resp.json()["access_token"]


# --------------------------------------------------------------------------
# Catalogue search
# --------------------------------------------------------------------------
def find_products(token: str):
    """
    Query the CDSE OData catalogue for the 2024 NDVI 300m 10-daily files.

    We filter by:
      - product name containing 'NDVI300' and the version tag (V2/V3)
      - ContentDate within the target year
    and page through all results.
    """
    headers = {"Authorization": f"Bearer {token}"}
    start = f"{YEAR}-01-01T00:00:00.000Z"
    end = f"{YEAR + 1}-01-01T00:00:00.000Z"

    flt = (
        "contains(Name,'NDVI300') "
        f"and contains(Name,'{PRODUCT_VERSION}') "
        f"and ContentDate/Start ge {start} "
        f"and ContentDate/Start lt {end}"
    )

    params = {
        "$filter": flt,
        "$orderby": "ContentDate/Start asc",
        "$top": "100",
    }

    products = []
    url = ODATA_URL
    first = True
    while url:
        resp = requests.get(
            url, headers=headers, params=params if first else None, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        products.extend(data.get("value", []))
        url = data.get("@odata.nextLink")  # pagination
        first = False

    return products


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------
def download_product(token: str, product: dict, dest: Path) -> Path:
    """Stream one product's NetCDF to disk via the OData $value endpoint."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"    already downloaded: {dest.name}")
        return dest

    pid = product["Id"]
    url = f"{ODATA_URL}({pid})/$value"
    headers = {"Authorization": f"Bearer {token}"}

    with requests.get(url, headers=headers, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
        tmp.rename(dest)
    return dest


# --------------------------------------------------------------------------
# Clip to San Francisco
# --------------------------------------------------------------------------
def clip_to_sf(nc_path: Path, out_path: Path):
    """Open a global NDVI NetCDF, slice to the SF bbox, and save the subset."""
    if xr is None:
        raise RuntimeError("xarray/netCDF4 not installed; run: pip install -r requirements.txt")

    ds = xr.open_dataset(nc_path)

    # Coordinate names vary slightly between products; detect them.
    lat_name = "lat" if "lat" in ds.coords else "latitude"
    lon_name = "lon" if "lon" in ds.coords else "longitude"

    # Latitude is stored north->south (descending) in CGLS products, so order
    # the slice bounds to match the coordinate's direction.
    lat_desc = bool(ds[lat_name][0] > ds[lat_name][-1])
    lat_slice = (
        slice(SF_BBOX["lat_max"], SF_BBOX["lat_min"])
        if lat_desc
        else slice(SF_BBOX["lat_min"], SF_BBOX["lat_max"])
    )
    lon_slice = slice(SF_BBOX["lon_min"], SF_BBOX["lon_max"])

    sub = ds.sel({lat_name: lat_slice, lon_name: lon_slice})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sub.to_netcdf(out_path)
    ds.close()
    sub.close()

    dims = {k: v for k, v in sub.sizes.items()}
    print(f"    clipped -> {out_path.name}  (dims: {dims})")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    username = os.environ.get("CDSE_USERNAME")
    password = os.environ.get("CDSE_PASSWORD")
    if not username or not password:
        sys.exit(
            "Missing credentials. Copy .env.example to .env and set "
            "CDSE_USERNAME and CDSE_PASSWORD.\n"
            "Register free at https://dataspace.copernicus.eu"
        )

    print("Authenticating with CDSE...")
    token = get_access_token(username, password)
    token_time = time.time()

    print(f"Searching catalogue for {YEAR} NDVI300 {PRODUCT_VERSION} products...")
    products = find_products(token)
    print(f"Found {len(products)} products (expected ~36 dekads).")
    if not products:
        sys.exit(
            "No products found. Try PRODUCT_VERSION='V3', or adjust the name "
            "filter in find_products() after inspecting a manual catalogue query."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(products, 1):
        name = p["Name"]
        print(f"[{i}/{len(products)}] {name}")

        # Refresh token roughly every 8 minutes (tokens expire ~10 min).
        if time.time() - token_time > 480:
            token = get_access_token(username, password)
            token_time = time.time()

        raw = download_product(token, p, RAW_DIR / name)
        clipped = OUT_DIR / (Path(name).stem + "_SF.nc")
        try:
            clip_to_sf(raw, clipped)
        except Exception as e:
            print(f"    WARNING: clip failed ({e}). Global file kept at {raw}")
            continue

        if not KEEP_GLOBAL_FILES:
            raw.unlink(missing_ok=True)

    print(f"\nDone. San Francisco NDVI subsets are in: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
