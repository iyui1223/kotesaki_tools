#!/bin/bash
#SBATCH --job-name=clim_monthly
#SBATCH --output=/soge-home/users/cenv1201/andante/cenv1201/scripts/kotesaki_tools/climatology/Log/clim_monthly.out
#SBATCH --error=/soge-home/users/cenv1201/andante/cenv1201/scripts/kotesaki_tools/climatology/Log/clim_monthly.err
#SBATCH --partition=Interactive
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=08:00:00

set -euo pipefail

source "../Const/env_settings_monthly.sh"

echo "============================================================"
echo "Monthly Climatology (WMO): ${CLIM_START_YEAR}-${CLIM_END_YEAR}"
echo "ERA5_MONTHLY: ${ERA5_MONTHLY}"
echo "MID_DIR: ${MID_DIR_MONTHLY}"
echo "OUTPUT_DIR: ${OUTPUT_DIR_MONTHLY}"
echo "============================================================"

mkdir -p "${OUTPUT_DIR_MONTHLY}" "${MID_DIR_MONTHLY}" "${LOG_DIR_MONTHLY}"

"${PYTHON}" "${ROOT_DIR}/Python/climatology_monthly_calc.py" \
  --config "${VARIABLES_CONFIG_MONTHLY}" \
  --era5-root "${ERA5_MONTHLY}" \
  --start-year "${CLIM_START_YEAR}" \
  --end-year "${CLIM_END_YEAR}" \
  --work-dir "${OUTPUT_DIR_MONTHLY}" \
  build-all

echo "Done monthly climatology"
