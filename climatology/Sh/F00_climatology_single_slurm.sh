#!/bin/bash
#SBATCH --job-name=clim
#SBATCH --output=/lustre/soge1/projects/andante/cenv1201/scripts/kotesaki_tools/climatology/Log/clim_T2m.out
#SBATCH --error=/lustre/soge1/projects/andante/cenv1201/scripts/kotesaki_tools/climatology/Log/clim_T2m.err
#SBATCH --partition=Medium
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#
# Single-variable climatology job.
# Submit via run_all_climatologies.sh which replaces %v with variable ID.
#
# Usage (direct):
#   VAR_ID=Z500 sbatch -D Sh F00_climatology_single_slurm.sh
# =============================================================================

set -euo pipefail

ROOT_DIR="/lustre/soge1/projects/andante/cenv1201/scripts/kotesaki_tools/climatology"
source "${ROOT_DIR}/Const/env_settings.sh"

VAR_ID="${VAR_ID:?Set VAR_ID (e.g. Z500, T2m, U850)}"

echo "============================================================"
echo "Climatology: ${VAR_ID}"
echo "============================================================"
echo "ERA5_DAILY: ${ERA5_DAILY}"
echo "OUTPUT_DIR: ${OUTPUT_DIR}"
echo "Period: ${CLIM_START_YEAR}-${CLIM_END_YEAR}"
echo "============================================================"

mkdir -p "${OUTPUT_DIR}" "${LOG_DIR}"

"${PYTHON}" "${ROOT_DIR}/Python/climatology_calc.py" "${VAR_ID}" \
  --config "${VARIABLES_CONFIG}" \
  --era5-root "${ERA5_DAILY}" \
  --start-year "${CLIM_START_YEAR}" \
  --end-year "${CLIM_END_YEAR}" \
  --output "${OUTPUT_DIR}/clim_${VAR_ID}_${CLIM_START_YEAR}-${CLIM_END_YEAR}.nc"

echo "Done: ${VAR_ID}"
