#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${APPTAINER:-singularity}"

"${RUNTIME}" pull "${SCRIPT_DIR}/gnina_singularity.sif" \
    oras://ghcr.io/jnelen/gnina_singularity:v1
