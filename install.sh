#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "Python >=3.11 required" >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python >=3.11 required"'
python3 -m venv "$root/.venv"
pip="$root/.venv/bin/python"
"$pip" -m pip install -e "$root"
"$pip" -c 'import lucida_api; print(lucida_api.API_VERSION)'
echo "API installed in $root/.venv"
