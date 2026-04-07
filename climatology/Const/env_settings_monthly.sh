#!/bin/bash
# =============================================================================
# Monthly Climatology Pipeline — Environment Settings
# =============================================================================

ROOT_DIR="/soge-home/users/cenv1201/andante/cenv1201/scripts/kotesaki_tools/climatology"

# ERA5 data root (monthly data)
export ERA5_ROOT="/lustre/soge1/data/analysis/era5/0.28125x0.28125"
export ERA5_MONTHLY="${ERA5_ROOT}/monthly"

# WMO climatology base period
export CLIM_START_YEAR=1991
export CLIM_END_YEAR=2020

# Output layout
export OUTPUT_DIR_MONTHLY="${ROOT_DIR}/climatology_monthly"
export MID_DIR_MONTHLY="${OUTPUT_DIR_MONTHLY}/mid"
export LOG_DIR_MONTHLY="${ROOT_DIR}/Log"

# Python
export PYTHON="${PYTHON:-python3}"

# Config
export VARIABLES_CONFIG_MONTHLY="${ROOT_DIR}/Const/variables_config_monthly.yaml"

mkdir -p "${OUTPUT_DIR_MONTHLY}" "${MID_DIR_MONTHLY}" "${LOG_DIR_MONTHLY}"
