#!/bin/bash
# =============================================================================
# Submit F00_climatology_single_slurm.sh for each variable via Slurm
# =============================================================================
# Each variable gets its own job, running in parallel on the cluster.
#
# Usage:
#   ./Sh/run_all_climatologies.sh              # all variables
#   ./Sh/run_all_climatologies.sh Z500 T2m     # selected variables only
# =============================================================================

set -euo pipefail

ROOT_DIR="/lustre/soge1/projects/andante/cenv1201/scripts/kotesaki_tools/climatology"
LOG_DIR="${ROOT_DIR}/Log"
mkdir -p "${LOG_DIR}"

VARS=(Z500 T2m U850 U500 U200 V850 V500 V200)
if [[ $# -gt 0 ]]; then
    VARS=("$@")
fi

echo "Submitting ${#VARS[@]} climatology jobs:"

for v in "${VARS[@]}"; do
    echo "  ${v}"
    VAR_ID="${v}" sbatch \
        --export=ALL,VAR_ID="${v}" \
        --job-name="clim_${v}" \
        --output="${LOG_DIR}/clim_${v}_%j.out" \
        --error="${LOG_DIR}/clim_${v}_%j.err" \
        "${ROOT_DIR}/Sh/F00_climatology_single_slurm.sh"
done

echo ""
echo "Done. Monitor with: squeue -u \$USER"
