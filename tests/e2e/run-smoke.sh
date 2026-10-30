#!/usr/bin/env bash
# Run the browser smoke test (delegates to the python runner, which picks
# Playwright if installed, otherwise a local Chrome/Edge).
set -euo pipefail
exec python "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke.py"
