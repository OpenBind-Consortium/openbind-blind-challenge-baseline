#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="https://sourceforge.net/projects/smina/files/smina.static/download"

wget -O "${SCRIPT_DIR}/smina" "${URL}"
chmod +x "${SCRIPT_DIR}/smina"
echo "Installed smina at ${SCRIPT_DIR}/smina"
