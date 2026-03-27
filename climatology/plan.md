## GRIB-First Climatology Refactor Plan (Hybrid `wgrib2` + `CDO` + Python)

### Summary
Refactor the current monolithic Python workflow into a two-stage production pipeline:
1) build reusable **unsmoothed daily climatology mid-files** (1990–2020) from GRIB inputs, and  
2) apply optional smoothing/filter products in a separate step.  
Tool split: `wgrib2` for fast GRIB slicing, `CDO` for heavy temporal aggregation and format handling, Python for orchestration, leap-day logic, metadata, and configurable filter plugins.

### Implementation Changes
1. **Pipeline architecture**
- Stage A (`build_mid`): produce NetCDF mid-files keyed by `variable × time_of_day × level` for each day-of-year.
- Stage B (`build_product`): combine selected mid-files and apply optional filters (Lanczos first, extensible to alternatives).
- Keep Stage A unsmoothed by default so future climatology definitions do not require re-reading all GRIB archives.

-- actually, Lancozs filter may have to be applied before combining time_of_day -- as we may want to retain high-frequency (daily frequency) but smooth out everything else. Think about that when we really need climatology with hourly resolution. By default we may use daily mean (average from each time_of_day) simply, as is conventional.

2. **Config and interfaces (decision-complete defaults)**
- Extend variable config to be GRIB-native:
  - input `data_subdir` and GRIB filename pattern
  - GRIB selectors (`shortName`, `typeOfLevel`, `level`, optional `step`)
  - output variable name and units metadata
- Add run config section for:
  - base period default `1990-01-01` to `2020-12-31`
  - `time_of_day` list default `[00, 06, 12, 18]`
  - level list (user-selectable, default per variable)
  - smoothing config (`method: none|lanczos|...`, defaults to `none` in Stage A)
- CLI split in Python (new subcommands):
  - `climatology_calc.py build-mid ...`
  - `climatology_calc.py build-product ...`

3. **Tool ownership per processing step**
- `wgrib2`:
  - inventory and select records by var/level/hour/year before decode-heavy work
