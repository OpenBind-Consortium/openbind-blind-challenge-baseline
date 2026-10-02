#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-1.3.2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="https://github.com/gnina/gnina/releases/download/v${VERSION}/gnina.${VERSION}"

wget -O "${SCRIPT_DIR}/gnina" "${URL}"
chmod +x "${SCRIPT_DIR}/gnina"
echo "Installed GNINA ${VERSION} at ${SCRIPT_DIR}/gnina"
