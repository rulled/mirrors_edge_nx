#!/usr/bin/env bash
# Builds the ReXGlue host code generator executable for your host machine (Linux, macOS, WSL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="$ROOT/sdk"
BUILD_DIR="${BUILD_DIR:-$SDK/out/build/host}"
CC="${CC:-clang}"
CXX="${CXX:-clang++}"
PYTHON="${PYTHON:-python3}"

if command -v nproc >/dev/null 2>&1; then
  DEFAULT_JOBS=$(nproc)
else
  DEFAULT_JOBS=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
fi
JOBS="${JOBS:-$DEFAULT_JOBS}"
CONFIGURE_ONLY=0
[[ "${1:-}" == "--configure" ]] && CONFIGURE_ONLY=1

for tool in cmake ninja "$CC" "$CXX"; do
  command -v "$tool" >/dev/null 2>&1 || { echo "error: '$tool' not found in PATH" >&2; exit 1; }
done

if [[ ! -f "$SDK/thirdparty/fmt/include/fmt/format.h" ]]; then
  echo "== fetching SDK third-party sources (tools/fetch_thirdparty.py)"
  "$PYTHON" "$ROOT/tools/fetch_thirdparty.py"
fi

echo "== configure ($BUILD_DIR)"
cmake -S "$SDK" -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$CC" -DCMAKE_CXX_COMPILER="$CXX"

[[ $CONFIGURE_ONLY -eq 1 ]] && { echo "configured; run tools/build_host.sh to build"; exit 0; }

echo "== building rexglue target"
cmake --build "$BUILD_DIR" --target rexglue -j "$JOBS"

built=""
for candidate in "$SDK"/out/*/rexglue "$SDK"/out/*/Release/rexglue; do
  [[ -x "$candidate" && "$candidate" != "$SDK/out/host/rexglue" ]] && { built="$candidate"; break; }
done
[[ -n "$built" ]] || { echo "error: rexglue executable not found under $SDK/out" >&2; exit 1; }

mkdir -p "$SDK/out/host"
ln -sfn "../${built#"$SDK/out/"}" "$SDK/out/host/rexglue"
echo "ok: $SDK/out/host/rexglue -> $built"
