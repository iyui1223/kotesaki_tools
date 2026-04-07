#!/usr/bin/env python3
"""
Climatology calculation with Lanczos low-pass filtering (Duchon 1979).

Computes smooth daily climatological normals:
  1. Accumulate daily values year-by-year for each day-of-year (excl. Feb 29)
  2. Apply Lanczos filter (121-term, 60-day cutoff) with circular boundary
  3. Derive leap-day value from smoothed Feb 28 and Mar 1
  4. Write NetCDF with climatological time axis (year 1900)
"""

from __future__ import annotations

import argparse
import gc
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


def doy_to_clim_date(doy: int) -> np.datetime64:
    """Convert day-of-year (1-366) to datetime64 in year 2000 for climatology.

    Year 2000 is used because it is a leap year (366 days).
    """
    return np.datetime64("2000-01-01") + np.timedelta64(doy - 1, "D")


# -----------------------------------------------------------------------------
# File discovery
# -----------------------------------------------------------------------------
def build_file_list_by_year(
    base_dir: Path,
    pattern: str,
    file_format: str,
    start_year: int,
    end_year: int,
) -> tuple[dict[int, list[Path]], list[Path]]:
    """
    Build dict of year -> file list, plus list of truly missing paths.

    Returns (files_by_year, missing).
    """
    files_by_year: dict[int, list[Path]] = {}
    missing: list[Path] = []

    for y in range(start_year, end_year + 1):
        year_files: list[Path] = []

        if file_format == "yearly":
            p = base_dir / pattern.format(year=y)
            if p.exists():
                year_files.append(p)
            else:
                g = sorted(base_dir.glob(pattern.replace("{year}", str(y))))
                if g:
                    year_files.extend(g)
                else:
                    missing.append(p)
        else:  # monthly
            for m in range(1, 13):
                p = base_dir / pattern.format(year=y, month=m)
                if p.exists():
                    year_files.append(p)
                else:
                    g = sorted(
                        base_dir.glob(
                            pattern.replace("{year}", str(y)).replace(
                                "{month:02d}", f"{m:02d}"
                            )
                        )
                    )
                    if g:
                        year_files.extend(g)
                    else:
                        missing.append(p)

        if year_files:
            files_by_year[y] = sorted(set(year_files))

    return files_by_year, missing


# -----------------------------------------------------------------------------
# Climatology computation (year-by-year accumulation)
# -----------------------------------------------------------------------------
def compute_climatology(
    files_by_year: dict[int, list[Path]],
    var: str,
    level_var: str | None,
    level: int | None,
    n_lanczos: int = 60,
    fc: float = 1.0 / 60.0,
) -> xr.DataArray:
    """
    Compute smooth daily climatological normals.

    Steps (following JMA / JRA-3Q operational practice):
      1. Accumulate daily values year-by-year for DOY 1..365, excluding Feb 29.
         Only one year is in memory at a time.
      2. Apply Lanczos low-pass filter with circular boundary.
      3. Insert leap day as mean of smoothed Feb 28 and Mar 1.

    Parameters
    ----------
    files_by_year : dict[int, list[Path]]
        Mapping from year to list of NetCDF file paths.
    var : str
        NetCDF variable name to read.
    level_var : str or None
        Name of the pressure level dimension, if applicable.
    level : int or None
        Single pressure level to select, if applicable.
    n_lanczos : int
        Half-window length (default 60 -> 121-term filter).
    fc : float
        Cutoff frequency in cycles per sample (default 1/60).
    """
    # --- Step 1: Year-by-year accumulation ---
    doy_sum: np.ndarray | None = None
    n_years = 0
    template_da: xr.DataArray | None = None

    for year in sorted(files_by_year):
        print(f"  Processing {year}...")
        ds = xr.open_mfdataset(
            [str(p) for p in files_by_year[year]],
            combine="by_coords",
        )
        da = ds[var]
        if level is not None and level_var and level_var in ds.dims:
            da = da.sel({level_var: level})

        # Drop Feb 29, load single year into memory
        _, valid = day_of_year_365(da.time)
        da_valid = da.where(valid, drop=True).load()

        ntime = da_valid.sizes["time"]
        if ntime != 365:
            print(
                f"  WARNING: year {year} has {ntime} valid days "
                f"(expected 365), skipping.",
                file=sys.stderr,
            )
            ds.close()
            continue

        year_data = da_valid.values.astype(np.float64)
        if doy_sum is None:
            doy_sum = year_data
            # Save a single-timestep slice for coords/dims reconstruction (no full-year data)
            template_da = da_valid.isel(time=0, drop=False).copy(deep=True)
        else:
            doy_sum += year_data
        del year_data, da_valid, da
        ds.close()
        del ds
        gc.collect()
        n_years += 1

    if doy_sum is None or n_years == 0:
        raise RuntimeError("No valid years processed.")

    print(f"  Averaged over {n_years} years.")
    clim_raw = doy_sum / n_years  # shape: (365, ...)
    del doy_sum
    gc.collect()

    # --- Step 2: Lanczos filter with circular (wrap) boundary ---
    w = lanczos_weights(n_lanczos, fc)
    clim_smooth = convolve1d(clim_raw, w, axis=0, mode="wrap")
    del clim_raw
    gc.collect()

    # --- Step 3: Insert leap day = mean(Feb 28, Mar 1) ---
    # Index 58 = DOY 59 = Feb 28, index 59 = DOY 60 = Mar 1
    leap = 0.5 * (clim_smooth[58] + clim_smooth[59])
    clim_366 = np.concatenate(
        [clim_smooth[:59], leap[np.newaxis], clim_smooth[59:]],
        axis=0,
    )  # shape: (366, ...)
    del clim_smooth
    gc.collect()

    # --- Build output DataArray with climatological time axis ---
    time_clim = np.array(
        [doy_to_clim_date(d) for d in range(1, 367)],
        dtype="datetime64[ns]",
    )
    spatial_coords = {
        k: v for k, v in template_da.coords.items() if k != "time"
    }
    spatial_dims = [d for d in template_da.dims if d != "time"]

    return xr.DataArray(
        clim_366,
        dims=["time"] + spatial_dims,
        coords={"time": time_clim, **spatial_coords},
        attrs=template_da.attrs,
        name=template_da.name,
    )


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
def write_climatology(
    da: xr.DataArray,
    out_path: Path,
    var_name: str,
) -> None:
    """Write climatology as plain NetCDF (year 2000 dates, standard calendar).

    The output is a regular NetCDF with 366 daily time steps spanning
    2000-01-01 to 2000-12-31.  GrADS should interpret it as climatological
    via a companion .ctl descriptor (see write_grads_ctl).
    """
    ds = da.to_dataset(name=var_name)
    ds.to_netcdf(out_path)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute Lanczos-smoothed climatology for ERA5 variable"
    )
    parser.add_argument(
        "var_id",
        choices=["Z500", "T2m", "U850", "U500", "U200", "V850", "V500", "V200", "T850", "T500", "T200"],
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

    # Build file list grouped by year
    files_by_year, missing = build_file_list_by_year(
        base_dir, vcfg["file_pattern"], vcfg["file_format"],
        args.start_year, args.end_year,
    )

    if missing:
        print("WARNING: Expected NetCDF files not found:", file=sys.stderr)
        for p in missing[:10]:
            print(f"  - {p}", file=sys.stderr)
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more", file=sys.stderr)

    if not files_by_year:
        print(
            f"ERROR: No input files found in {base_dir} "
            f"for {args.start_year}-{args.end_year}",
            file=sys.stderr,
        )
        return 1

    all_files = [f for flist in files_by_year.values() for f in flist]
    print(f"Variable: {args.var_id}")
    print(f"Years: {min(files_by_year)}-{max(files_by_year)} ({len(files_by_year)} years)")
    print(f"Files: {len(all_files)} total")

    if args.dry_run:
        print(f"\nDry run — found {len(all_files)} files (first 10):")
        for p in all_files[:10]:
            print(f"  - {p}")
        if len(all_files) > 10:
            print(f"  ... and {len(all_files) - 10} more")
        return 0

    # Resolve single level (squeeze level dim for single-level variables)
    levels = vcfg.get("levels")
    level = levels[0] if levels and len(levels) == 1 else None

    # Compute climatology (year-by-year, low memory)
    clim = compute_climatology(
        files_by_year,
        vcfg["nc_var"],
        vcfg.get("level_var"),
        level,
        n_lanczos=args.n_lanczos,
    )

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
