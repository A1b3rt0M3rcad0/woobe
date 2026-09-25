#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT=".test-artifacts/package-build"
DIST="$OUT/dist"
rm -rf "$OUT"
mkdir -p "$DIST/core" "$DIST/api" "$DIST/workers"

uv build packages/woobe-core --out-dir "$DIST/core"
uv build packages/woobe-api --out-dir "$DIST/api"
uv build packages/woobe-workers --out-dir "$DIST/workers"

require_artifacts() {
  local dir="$1"
  local wheel_pattern="$2"
  test -n "$(find "$dir" -maxdepth 1 -name "$wheel_pattern" -print -quit)"
  test -n "$(find "$dir" -maxdepth 1 -name '*.tar.gz' -print -quit)"
}

require_artifacts "$DIST/core" 'woobe_core-*.whl'
require_artifacts "$DIST/api" 'woobe_api-*.whl'
require_artifacts "$DIST/workers" 'woobe_workers-*.whl'

clean_venv() {
  local name="$1"
  local venv="$OUT/venv-$name"
  rm -rf "$venv"
  uv venv "$venv" --python 3.14 >/dev/null
  printf '%s\n' "$venv"
}

core_venv="$(clean_venv core)"
uv pip install --python "$core_venv/bin/python" "$DIST/core"/woobe_core-*.whl
"$core_venv/bin/python" -c "from importlib.metadata import version; import modules, shared; assert version('woobe-core')"
uv pip check --python "$core_venv/bin/python"

api_venv="$(clean_venv api)"
uv pip install --python "$api_venv/bin/python" --find-links "$DIST/core" "$DIST/api"/woobe_api-*.whl
"$api_venv/bin/python" -c "from importlib.metadata import version; from importlib.util import find_spec; import woobe_api; assert find_spec('main'); assert find_spec('woobe_workers') is None; assert version('woobe-api') == version('woobe-core')"
uv pip check --python "$api_venv/bin/python"

workers_venv="$(clean_venv workers)"
uv pip install --python "$workers_venv/bin/python" --find-links "$DIST/core" "$DIST/workers"/woobe_workers-*.whl
"$workers_venv/bin/python" -c "from importlib.metadata import version; from importlib.util import find_spec; import woobe_workers; assert find_spec('worker_main'); assert find_spec('woobe_api') is None; assert version('woobe-workers') == version('woobe-core')"
uv pip check --python "$workers_venv/bin/python"

echo "Python package artifacts built and clean-installed successfully."
