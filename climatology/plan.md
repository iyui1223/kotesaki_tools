## GRIB-First Climatology Refactor Plan (Hybrid `eccode` + `CDO` + Python)

### Summary
Refactor the current monolithic Python workflow into a two-stage production pipeline:
1) build reusable **unsmoothed daily climatology mid-files** (1990–2020) from GRIB inputs, and  
2) apply optional smoothing/filter products in a separate step.  
Tool split: `eccode` for fast GRIB slicing, `CDO` for heavy temporal aggregation and format handling, Python for orchestration, leap-day logic, metadata, and configurable filter plugins.
currently miniconda based venv with eccode is available at 
conda activate grib_env.
Install additional tools for python to perform the filtering in that venv.


We need both grib and nc handling -- this is because the admin decided that we may want to switchc to grib and netcdf data will soon all be discarded. (no one knows when exactly, and lots of grib/netcdf files are incomplete -- sadly we are asked to combine dual inputs at hand to do any kind of data analysis which is infinitely stupid chaos -- but we can still plan to make it at least work for environment with grib. Certain variables are more complete in nc, whereas others grib has better availability -- unfortunately chaos dominates everything) Probably climatology directory may want to be kept this way, but another clomatology_grib/ dir to take over later should be initiated for the new grib based workflow.

Here are the changes from the current nc based work flow, which not just is about input format change, but some improvements of efficiency and modularity.

### Implementation Changes
1. **Pipeline architecture**
- Stage A (`build_mid`): produce NetCDF mid-files keyed by `variable × time_of_day × level` for each day-of-year. That way each day/level/time_of_day process can be pararellized and more faster to execute.

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
