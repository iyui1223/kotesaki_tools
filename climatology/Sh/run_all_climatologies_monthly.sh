#!/bin/bash
# =============================================================================
# Submit monthly climatology build jobs via Slurm
# =============================================================================

set -euo pipefail

ROOT_DIR="/lustre/soge1/projects/andante/cenv1201/scripts/kotesaki_tools/climatology"
LOG_DIR="${ROOT_DIR}/Log"
mkdir -p "${LOG_DIR}"

echo "Submitting monthly climatology job (WMO 1991-2020):"
sbatch \
  --job-name="clim_monthly" \
  --output="${LOG_DIR}/clim_monthly_%j.out" \
  --error="${LOG_DIR}/clim_monthly_%j.err" \
  "${ROOT_DIR}/Sh/F00_climatology_monthly_single_slurm.sh"

echo "Done. Monitor with: squeue -u \$USER"
