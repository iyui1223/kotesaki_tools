#!/bin/bash
# =============================================================================
# Climatology Pipeline — Environment Settings
# =============================================================================
# Used by Sh/*.sh scripts. Source from project root.
# =============================================================================

# ERA5 data root (daily data)
export ERA5_ROOT="/lustre/soge1/data/analysis/era5/0.28125x0.28125"
export ERA5_DAILY="${ERA5_ROOT}/daily"


# Climatology base period
export CLIM_START_YEAR=1991
export CLIM_END_YEAR=2020

# Output
export OUTPUT_DIR="${ROOT_DIR}/climatology"
export LOG_DIR="${ROOT_DIR}/Log"

# Python (activate venv if needed, or use system python)
export PYTHON="${PYTHON:-python3}"

# Config
export VARIABLES_CONFIG="${ROOT_DIR}/Const/variables_config.yaml"

# Create dirs
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${LOG_DIR}"
