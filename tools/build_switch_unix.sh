#!/usr/bin/env bash
# Builds Mirror's Edge for Nintendo Switch (devkitA64 + libnx + NVK)
set -euo pipefail
if [[ "$0" == /tmp/* ]]; then
  ROOT="${ROOT:-/mnt/e/MirrorsEdge_NX}"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
export DEVKITPRO="${DEVKITPRO:-/opt/devkitpro}"
export DEVKITA64="${DEVKITPRO}/devkitA64"
export PATH="${DEVKITA64}/bin:${DEVKITPRO}/tools/bin:${PATH}"

BUILD_DIR="${BUILD_DIR:-$ROOT/out/build/switch_app}"
NVK_SDK="${REXGLUE_SWITCH_NVK_SDK:-$ROOT/tools/mesa-sdk/opt/devkitpro/portlibs/switch}"
TOOLCHAIN="$ROOT/tools/switch/cmake/switch-devkitA64.cmake"

echo "== Configuring Mirror's Edge NX for Nintendo Switch =="
echo "DEVKITPRO: $DEVKITPRO"
echo "NVK_SDK:   $NVK_SDK"
echo "BUILD_DIR: $BUILD_DIR"

mkdir -p "$BUILD_DIR"

cmake -S "$ROOT/app" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_MAKE_PROGRAM=/usr/bin/ninja \
  -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
  -DREXGLUE_SWITCH_NVK_SDK="$NVK_SDK" \
  -DCMAKE_BUILD_TYPE=Release

echo "== Building mirrorsedge target =="
cmake --build "$BUILD_DIR" --target mirrorsedge -j "$(nproc)"
