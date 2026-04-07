#!/usr/bin/env python3
"""Monthly-to-daily climatology builder (WMO 1991-2020, GRIB-first).

Pipeline:
  1) build-mid: create one monthly climatology file per pressure level
               (12 x lat x lon)
  2) build-product: read per-level mid files, linearly interpolate monthly
               climatology to daily (year 2000, 366 days), then combine
               all levels into one final output.

Memory safety:
  - Never keeps a year-stacked temporal cube in memory.
  - build-mid relies on CDO streaming operators.
  - build-product loads one level's 12-month field at a time.
"""

from __future__ import annotations

import argparse
import calendar
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import netCDF4 as nc
import numpy as np
import xarray as xr
import yaml


@dataclass
class MonthlyConfig:
    data_subdir: str
    file_pattern: str
    short_name: str
    type_of_level: str
    levels_hpa: list[int]
    levels_pa: list[int]
    output_var: str


def run_cmd(cmd: list[str], dry_run: bool = False) -> None:
    print("+", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def load_config(path: Path) -> MonthlyConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    cfg = raw["monthly"]
    return MonthlyConfig(
        data_subdir=cfg["data_subdir"],
        file_pattern=cfg["file_pattern"],
        short_name=cfg["short_name"],
        type_of_level=cfg["type_of_level"],
        levels_hpa=[int(v) for v in cfg["levels_hpa"]],
        levels_pa=[int(v) for v in cfg["levels_pa"]],
        output_var=cfg.get("output_var", cfg["short_name"]),
    )


def discover_month_files(
    base_dir: Path,
    pattern: str,
    start_year: int,
    end_year: int,
) -> tuple[dict[int, list[Path]], list[str]]:
    files_by_month: dict[int, list[Path]] = {m: [] for m in range(1, 13)}
    missing: list[str] = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            expected = base_dir / pattern.format(year=year, month=month)
            if expected.exists() and expected.suffix == ".grb":
                files_by_month[month].append(expected)
            else:
                missing.append(f"{year}-{month:02d}: {expected}")

    return files_by_month, missing


def ensure_complete_month_coverage(
    files_by_month: dict[int, list[Path]],
    start_year: int,
    end_year: int,
) -> None:
    expected = end_year - start_year + 1
    bad = [m for m in range(1, 13) if len(files_by_month[m]) != expected]
    if bad:
        details = ", ".join([f"{m:02d}({len(files_by_month[m])}/{expected})" for m in bad])
        raise RuntimeError(
            f"Monthly coverage incomplete for months: {details}. "
            "Refusing to build climatology with missing years."
        )


def build_mid(
    cfg: MonthlyConfig,
    era5_root: Path,
    start_year: int,
    end_year: int,
    work_dir: Path,
    dry_run: bool,
) -> None:
    base_dir = era5_root / cfg.data_subdir
    mid_dir = work_dir / "mid"
    mid_dir.mkdir(parents=True, exist_ok=True)

    files_by_month, missing = discover_month_files(
        base_dir, cfg.file_pattern, start_year, end_year
    )

    print(f"Input directory: {base_dir}")
    print(f"Period: {start_year}-{end_year}")
    for month in range(1, 13):
        print(f"  month {month:02d}: {len(files_by_month[month])} files")

    if missing:
        print("WARNING: missing files detected (showing first 20):", file=sys.stderr)
        for line in missing[:20]:
            print(f"  - {line}", file=sys.stderr)
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more", file=sys.stderr)

    ensure_complete_month_coverage(files_by_month, start_year, end_year)

    if dry_run:
        print("Dry run complete: monthly coverage is complete.")
        return

    with TemporaryDirectory(prefix="clim_monthly_mid_") as tdir:
        tmp = Path(tdir)
        monthly_mean_files: dict[int, Path] = {}

        # Step 1: For each month-of-year, compute mean across 1991-2020 ensemble.
        for month in range(1, 13):
            out_m = tmp / f"mean_month_{month:02d}_all_levels.nc"
            cmd = [
                "cdo",
                "-O",
                "-f",
                "nc",
                "ensmean",
                *[str(p) for p in files_by_month[month]],
                str(out_m),
            ]
            run_cmd(cmd, dry_run=False)
            monthly_mean_files[month] = out_m

        # Step 2: Save one mid-product per requested level (12 x lat x lon).
        for level_hpa, level_pa in zip(cfg.levels_hpa, cfg.levels_pa):
            per_month_level: list[Path] = []
            for month in range(1, 13):
                out_lm = tmp / f"lev_{level_hpa:04d}hPa_m{month:02d}.nc"
                # NOTE:
                #   CDO 2.4.x on this system does not accept typeOfLevel in
                #   the generic -select key list ("Unsupported selection keyword").
                #   Use selname + sellevel, which is supported and sufficient
                #   for ERA5 temperature pressure-level inputs.
                cmd = [
                    "cdo",
                    "-O",
                    "-f",
                    "nc",
                    f"-selname,{cfg.short_name}",
                    f"-sellevel,{level_pa}",
                    str(monthly_mean_files[month]),
                    str(out_lm),
                ]
                run_cmd(cmd, dry_run=False)
                per_month_level.append(out_lm)

            merged = tmp / f"monthly_clim_t_{level_hpa:04d}hPa_merged.nc"
            run_cmd(
                ["cdo", "-O", "mergetime", *[str(p) for p in per_month_level], str(merged)],
                dry_run=False,
            )

            out_mid = mid_dir / f"monthly_clim_t_{level_hpa:04d}hPa_{start_year}-{end_year}.nc"
            run_cmd(["cdo", "-O", "setyear,2000", str(merged), str(out_mid)], dry_run=False)
            print(f"Wrote mid-product: {out_mid}")


def iter_daily_fields_from_monthly(
    monthly_values: np.ndarray,
    year: int = 2000,
):
    """Yield daily fields via linear monthly->daily interpolation.

    monthly_values shape: (12, lat, lon)
    yields tuples: (day_index, field_2d)
    """
    nday = 366 if calendar.isleap(year) else 365
    d0 = date(year, 1, 1)

    for i in range(nday):
        d = d0 + timedelta(days=i)
        m = d.month
        m0_idx = m - 1
        m1_idx = 0 if m == 12 else m

        m_start = date(year, m, 1)
        if m == 12:
            m_next = date(year + 1, 1, 1)
        else:
            m_next = date(year, m + 1, 1)

        w = (d - m_start).days / (m_next - m_start).days
        field = (1.0 - w) * monthly_values[m0_idx] + w * monthly_values[m1_idx]
        yield i, field.astype(np.float32, copy=False)


def _pick_lat_lon_names(ds: xr.Dataset) -> tuple[str, str]:
    lat_candidates = ["lat", "latitude"]
    lon_candidates = ["lon", "longitude"]

    lat_name = next((n for n in lat_candidates if n in ds.coords), None)
    lon_name = next((n for n in lon_candidates if n in ds.coords), None)

    if lat_name is None or lon_name is None:
        raise RuntimeError("Could not identify latitude/longitude coordinate names.")

    return lat_name, lon_name


def build_product(
    cfg: MonthlyConfig,
    start_year: int,
    end_year: int,
    work_dir: Path,
    output: Path | None,
    interp: str,
    dry_run: bool,
) -> None:
    if interp != "linear":
        raise ValueError("Only --interp linear is supported in this implementation.")

    mid_dir = work_dir / "mid"
    level_mid_files = [
        mid_dir / f"monthly_clim_t_{lev:04d}hPa_{start_year}-{end_year}.nc"
        for lev in cfg.levels_hpa
    ]

    missing_mid = [p for p in level_mid_files if not p.exists()]
    if missing_mid:
        raise RuntimeError(
            "Missing mid-product files. Run build-mid first. Missing examples: "
            + ", ".join(str(p) for p in missing_mid[:5])
        )

    out_path = (
        output
        if output is not None
        else work_dir / f"clim_daily_t_plev_{start_year}-{end_year}_{interp}.nc"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print("Dry run complete: all per-level mid products are available.")
        print(f"Would write: {out_path}")
        return

    # Use first level mid file as template for grid/coords.
    with xr.open_dataset(level_mid_files[0]) as ds0:
        lat_name, lon_name = _pick_lat_lon_names(ds0)
        lat = ds0[lat_name].values
        lon = ds0[lon_name].values

    ntime = 366
    nlev = len(cfg.levels_hpa)

    with nc.Dataset(out_path, "w", format="NETCDF4") as ds_out:
        ds_out.createDimension("time", ntime)
        ds_out.createDimension("level", nlev)
        ds_out.createDimension(lat_name, lat.shape[0])
        ds_out.createDimension(lon_name, lon.shape[0])

        time_var = ds_out.createVariable("time", "f8", ("time",))
        level_var = ds_out.createVariable("level", "i4", ("level",))
        lat_var = ds_out.createVariable(lat_name, "f4", (lat_name,))
        lon_var = ds_out.createVariable(lon_name, "f4", (lon_name,))

        out_var = ds_out.createVariable(
            cfg.output_var,
            "f4",
            ("time", "level", lat_name, lon_name),
            zlib=True,
            complevel=4,
            shuffle=True,
            chunksizes=(1, 1, lat.shape[0], lon.shape[0]),
        )

        # Coordinate metadata
        time_var.units = "days since 2000-01-01 00:00:00"
        time_var.calendar = "proleptic_gregorian"
        time_var.long_name = "climatological time"

        level_var.units = "hPa"
        level_var.long_name = "pressure_level"

        lat_var[:] = lat.astype(np.float32)
        lon_var[:] = lon.astype(np.float32)
        level_var[:] = np.asarray(cfg.levels_hpa, dtype=np.int32)

        # 2000-01-01 .. 2000-12-31
        dates = [datetime(2000, 1, 1) + timedelta(days=i) for i in range(ntime)]
        time_var[:] = nc.date2num(dates, units=time_var.units, calendar=time_var.calendar)

        ds_out.title = (
            f"Daily climatology from monthly means ({start_year}-{end_year}, {interp} interpolation)"
        )
        ds_out.history = "Created by climatology_monthly_calc.py"

        # Process one level at a time (memory-safe w.r.t year-stacked time dimension)
        for lev_idx, (lev_hpa, mid_path) in enumerate(zip(cfg.levels_hpa, level_mid_files)):
            print(f"Interpolating level {lev_hpa} hPa from {mid_path}")
            with xr.open_dataset(mid_path) as ds_mid:
                da = ds_mid[cfg.output_var]
                if da.sizes.get("time", -1) != 12:
                    raise RuntimeError(
                        f"Mid-product {mid_path} has time={da.sizes.get('time')} (expected 12)."
                    )
                monthly_values = da.values.astype(np.float32)

            for day_idx, field in iter_daily_fields_from_monthly(monthly_values, year=2000):
                out_var[day_idx, lev_idx, :, :] = field

    print(f"Wrote final product: {out_path}")


def add_common_args(p: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
    """Add shared CLI options.

    We add these to both root and subparsers so users can place options
    either before or after the subcommand.
    """
    default_config = argparse.SUPPRESS if suppress_defaults else str(
        Path(__file__).resolve().parent.parent / "Const" / "variables_config_monthly.yaml"
    )
    default_era5_root = argparse.SUPPRESS if suppress_defaults else "/lustre/soge1/data/analysis/era5/0.28125x0.28125/monthly"
    default_start_year = argparse.SUPPRESS if suppress_defaults else 1991
    default_end_year = argparse.SUPPRESS if suppress_defaults else 2020
    default_work_dir = argparse.SUPPRESS if suppress_defaults else str(
        Path(__file__).resolve().parent.parent / "climatology_monthly"
    )
    default_interp = argparse.SUPPRESS if suppress_defaults else "linear"
    default_output = argparse.SUPPRESS if suppress_defaults else None

    p.add_argument(
        "--config",
        default=default_config,
        help="Path to monthly variables config YAML",
    )
    p.add_argument(
        "--era5-root",
        default=default_era5_root,
        help="ERA5 monthly data root",
    )
    p.add_argument("--start-year", type=int, default=default_start_year)
    p.add_argument("--end-year", type=int, default=default_end_year)
    p.add_argument(
        "--work-dir",
        default=default_work_dir,
        help="Working/output root (contains mid/ and final product)",
    )
    p.add_argument(
        "--interp",
        choices=["linear"],
        default=default_interp,
        help="Monthly to daily interpolation method",
    )
    p.add_argument("--output", default=default_output, help="Final output path (build-product/build-all)")
    dry_run_default = argparse.SUPPRESS if suppress_defaults else False
    p.add_argument("--dry-run", action="store_true", default=dry_run_default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build WMO monthly climatology mid-products and daily product"
    )
    add_common_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)
    sp_mid = sub.add_parser("build-mid", help="Build per-level monthly climatology mid-products")
    sp_prod = sub.add_parser(
        "build-product",
        help="Build final daily multi-level climatology from mid-products",
    )
    sp_all = sub.add_parser("build-all", help="Run build-mid then build-product")

    # Allow options after subcommand as well.
    add_common_args(sp_mid, suppress_defaults=True)
    add_common_args(sp_prod, suppress_defaults=True)
    add_common_args(sp_all, suppress_defaults=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must be <= end-year")

    cfg = load_config(Path(args.config))

    if len(cfg.levels_hpa) != len(cfg.levels_pa):
        raise ValueError("levels_hpa and levels_pa length mismatch in config")

    work_dir = Path(args.work_dir)
    era5_root = Path(args.era5_root)
    out_path = Path(args.output) if args.output else None

    if args.command in ("build-mid", "build-all"):
        build_mid(
            cfg=cfg,
            era5_root=era5_root,
            start_year=args.start_year,
            end_year=args.end_year,
            work_dir=work_dir,
            dry_run=args.dry_run,
        )

    # In dry-run mode, build-all validates stage A inputs only and does not
    # require pre-existing mid-products for stage B.
    if args.command == "build-all" and args.dry_run:
        print("Dry run: skipped build-product because mid-products were not generated.")
        return 0

    if args.command in ("build-product", "build-all"):
        build_product(
            cfg=cfg,
            start_year=args.start_year,
            end_year=args.end_year,
            work_dir=work_dir,
            output=out_path,
            interp=args.interp,
            dry_run=args.dry_run,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
