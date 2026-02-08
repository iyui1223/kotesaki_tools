#!/usr/bin/env python3
"""
Climatology calculation with Lanczos low-pass filtering (Duchon 1979).

Computes smooth daily climatological normals:
  1. Average daily values over base period for each day-of-year (excl. leap days)
  2. Apply Lanczos filter (121-term, 60-day cutoff) with circular boundary
  3. Derive leap-day value from Feb 28 and Mar 1
  4. Write NetCDF with climatological time axis (year 1900)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import xarray as xr
import yaml
from scipy.ndimage import convolve1d


# -----------------------------------------------------------------------------
# Lanczos filter (Duchon 1979)
# -----------------------------------------------------------------------------
def lanczos_weights(n: int, fc: float) -> np.ndarray:
    """
    Compute Lanczos low-pass filter weights.

    Parameters
    ----------
    n : int
        Half-window length; full window = 2*n+1 (e.g. 121 for n=60).
    fc : float
        Cutoff frequency in cycles per sample.
        For 60-day cutoff with daily data: fc = 1/60.

    Returns
    -------
    w : ndarray, shape (2*n+1,)
        Normalized weights summing to 1.
    """
    k = np.arange(-n, n + 1, dtype=float)
    # np.sinc(x) = sin(pi*x) / (pi*x) with sinc(0)=1, no division warnings
    s1 = np.sinc(k * fc)   # ideal low-pass response
    s2 = np.sinc(k / n)    # Lanczos sigma factor
    w = s1 * s2
    w /= w.sum()
    return w


# -----------------------------------------------------------------------------
# Day-of-year and leap-day handling
# -----------------------------------------------------------------------------
def day_of_year_365(dates: xr.DataArray) -> tuple[xr.DataArray, xr.DataArray]:
    """
    Map datetime64 to day-of-year 1..365 (no leap day).

    Returns (doy_365, valid_mask) where Feb 29 is excluded.

    - Non-leap: doy 1..365 unchanged, all valid
    - Leap: doy 1..59 unchanged, Feb 29 excluded, Mar 1 onward shifted down by 1
    """
    month = dates.dt.month
    day = dates.dt.day
    doy = dates.dt.dayofyear
    is_leap = dates.dt.is_leap_year
    is_feb29 = (month == 2) & (day == 29)
    valid = ~is_feb29
    # For leap years, shift days after Feb down by 1
    doy_365 = xr.where(is_leap & (month > 2), doy - 1, doy)
    return doy_365, valid


def doy_to_date_1900(doy: int) -> np.datetime64:
    """Convert day-of-year (1-366) to datetime64 in year 1900 for climatology."""
    return np.datetime64("1900-01-01") + np.timedelta64(doy - 1, "D")


# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------
def load_and_aggregate(
    file_list: list[Path],
    var: str,
    level_var: str | None,
    levels: list[int] | None,
) -> xr.DataArray:
    """Load NetCDF files, select single level if needed, return chunked DataArray."""
    ds = xr.open_mfdataset(
        [str(p) for p in file_list],
        combine="by_coords",
        chunks={"time": 365},
        parallel=True,
    )
    da = ds[var]
    if levels is not None and level_var and level_var in ds.dims:
        # Select as scalar to squeeze out the level dimension entirely,
        # so we work with (time, lat, lon) not (time, 1, lat, lon).
        if len(levels) == 1:
            da = da.sel({level_var: levels[0]})
        else:
            da = da.sel({level_var: levels})
    print(f"  Loaded: {da.dims}, shape={da.shape}, chunks={da.chunks}")
    return da


def build_file_list(
    base_dir: Path,
    pattern: str,
    file_format: str,
    start_year: int,
    end_year: int,
) -> tuple[list[Path], list[Path]]:
    """
    Build list of input files from pattern and year range.

    Returns (found, missing) where missing only contains paths
    that could not be resolved by either direct match or glob.
    """
    files: list[Path] = []
    missing: list[Path] = []
    if file_format == "yearly":
        for y in range(start_year, end_year + 1):
            p = base_dir / pattern.format(year=y)
            if p.exists():
                files.append(p)
            else:
                g = list(base_dir.glob(pattern.replace("{year}", str(y))))
                if g:
                    files.extend(g)
                else:
                    missing.append(p)
    else:
        for y in range(start_year, end_year + 1):
            for m in range(1, 13):
                p = base_dir / pattern.format(year=y, month=m)
                if p.exists():
                    files.append(p)
                else:
                    g = list(
                        base_dir.glob(
                            pattern.replace("{year}", str(y)).replace(
                                "{month:02d}", f"{m:02d}"
                            )
                        )
                    )
                    if g:
                        files.extend(g)
                    else:
                        missing.append(p)
    return sorted(set(files)), missing


def write_climatology(
    da: xr.DataArray,
    out_path: Path,
    var_name: str,
) -> None:
    """Write climatology to NetCDF with climatological time axis (year 1900)."""
    ds = da.to_dataset(name=var_name)
    ds.time.attrs["calendar"] = "366_day"
    ds.time.attrs["axis"] = "T"
    ds.to_netcdf(out_path)


# -----------------------------------------------------------------------------
# Climatology computation
# -----------------------------------------------------------------------------
def compute_climatology(
    da: xr.DataArray,
    n_lanczos: int = 60,
    fc: float = 1.0 / 60.0,
) -> xr.DataArray:
    """
    Compute smooth daily climatological normals.

    Steps (following JMA / JRA-3Q operational practice):
      1. Average daily values by day-of-year (1..365), excluding Feb 29.
      2. Apply Lanczos low-pass filter with circular boundary.
      3. Insert leap day as mean of smoothed Feb 28 and Mar 1.

    Parameters
    ----------
    da : xr.DataArray
        Input daily data with a 'time' dimension.
    n_lanczos : int
        Half-window length (default 60 -> 121-term filter).
    fc : float
        Cutoff frequency in cycles per sample (default 1/60).
    """
    time_dim = "time"
    if time_dim not in da.dims:
        raise ValueError(f"No 'time' dimension in DataArray: {da.dims}")

    # --- Step 1: DOY average (dask-friendly via xarray groupby) ---
    doy_365, valid = day_of_year_365(da[time_dim])
    da_valid = da.where(valid, drop=True)
    doy_365 = doy_365.where(valid, drop=True).rename("doy")
    da_valid = da_valid.assign_coords(doy=doy_365)

    print("  Computing DOY means (1..365)...")
    clim_raw = da_valid.groupby("doy").mean(time_dim, skipna=True)
    clim_raw = clim_raw.load()  # materialize: only 365 slices, fits in memory
    clim_raw = clim_raw.assign_coords(doy=np.arange(1, 366))

    # --- Step 2: Lanczos filter with circular (wrap) boundary ---
    w = lanczos_weights(n_lanczos, fc)
    doy_axis = clim_raw.dims.index("doy")
    clim_smooth_values = convolve1d(
        clim_raw.values.astype(np.float64), w, axis=doy_axis, mode="wrap"
    )
    clim_smooth = clim_raw.copy(data=clim_smooth_values)

    # --- Step 3: Insert leap day = mean(Feb 28, Mar 1) ---
    leap = 0.5 * (clim_smooth.sel(doy=59) + clim_smooth.sel(doy=60))
    leap = leap.expand_dims({"doy": [60]})
    pre = clim_smooth.sel(doy=slice(1, 59))
    post = clim_smooth.sel(doy=slice(60, 365))
    clim_366 = xr.concat(
        [pre, leap, post], dim="doy", coords="minimal", compat="override"
    )
    clim_366 = clim_366.assign_coords(doy=np.arange(1, 367))

    # --- Build climatological time axis (year 1900) ---
    time_clim = np.array(
        [doy_to_date_1900(d) for d in range(1, 367)],
        dtype="datetime64[ns]",
    )
    clim_366 = clim_366.rename({"doy": time_dim})
    clim_366 = clim_366.assign_coords({time_dim: time_clim})
    return clim_366


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute Lanczos-smoothed climatology for ERA5 variable"
    )
    parser.add_argument(
        "var_id",
        choices=["Z500", "T2m", "U850", "U500", "U200", "V850", "V500", "V200"],
        help="Variable ID (as defined in variables_config.yaml)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to variables_config.yaml",
    )
    parser.add_argument(
        "--era5-root",
        default=None,
        help="ERA5 daily data root (overrides ERA5_DAILY env var)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1991,
        help="Climatology start year",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2020,
        help="Climatology end year",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output NetCDF path",
    )
    parser.add_argument(
        "--n-lanczos",
        type=int,
        default=60,
        help="Lanczos half-window (full = 2n+1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list expected input files and exit",
    )
    args = parser.parse_args()

    # Load config
    config_path = (
        Path(args.config)
        if args.config
        else Path(__file__).resolve().parent.parent / "Const" / "variables_config.yaml"
    )
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    vcfg = cfg["variables"][args.var_id]
    era5_root = (
        Path(args.era5_root)
        if args.era5_root
        else Path(
            os.environ.get(
                "ERA5_DAILY",
                "/lustre/soge1/data/analysis/era5/0.28125x0.28125/daily",
            )
        )
    )
    base_dir = era5_root / vcfg["data_subdir"]

    # Build file list
    files, missing = build_file_list(
        base_dir, vcfg["file_pattern"], vcfg["file_format"],
        args.start_year, args.end_year,
    )

    if missing:
        print("WARNING: Expected NetCDF files not found:", file=sys.stderr)
        for p in missing[:10]:
            print(f"  - {p}", file=sys.stderr)
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more", file=sys.stderr)

    if not files:
        print(
            f"ERROR: No input files found in {base_dir} "
            f"for {args.start_year}-{args.end_year}",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print(f"Dry run for {args.var_id}")
        print(f"Base dir: {base_dir}")
        print(f"Found {len(files)} files (first 10):")
        for p in files[:10]:
            print(f"  - {p}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")
        return 0

    # Load
    da = load_and_aggregate(
        files,
        vcfg["nc_var"],
        vcfg.get("level_var"),
        vcfg.get("levels"),
    )

    # Compute climatology
    clim = compute_climatology(da, n_lanczos=args.n_lanczos)

    # Output path
    out_path = (
        Path(args.output)
        if args.output
        else Path(os.environ.get("OUTPUT_DIR", "."))
        / f"clim_{args.var_id}_{args.start_year}-{args.end_year}.nc"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_climatology(clim, out_path, vcfg["output_var"])
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
