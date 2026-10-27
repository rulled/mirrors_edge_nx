#!/usr/bin/env bash
# Translates Mirror's Edge (default.xex) to C++ using ReXGlue host code generator.
# Input:  assets/game_root/default.xex
#         app/mirrorsedge_manifest.toml
# Output: app/generated/default/ (C++ sources and generated/rexglue.cmake)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/app"
PY="${PYTHON:-python3}"
REXGLUE="${REXGLUE:-$ROOT/sdk/out/host/rexglue}"
MANIFEST_NAME=mirrorsedge_manifest.toml
GEN="$APP/generated/default"

[[ -x "$REXGLUE" ]] || { echo "error: $REXGLUE not found; run tools/build_host.sh (or set REXGLUE)" >&2; exit 1; }
[[ -f "$APP/$MANIFEST_NAME" ]] || { echo "error: $APP/$MANIFEST_NAME not found" >&2; exit 1; }
XEX="${XEX:-$ROOT/assets/game_root/default.xex}"
[[ -f "$XEX" ]] || { echo "error: $XEX not found; extract your disc with tools/extract_iso.py first" >&2; exit 1; }

mkdir -p "$ROOT/out"
echo "== codegen ($APP/$MANIFEST_NAME)"
# The stamp only covers the declared inputs, not the generator binary: after changing the SDK pass
# IGNORE_STAMP=1, otherwise the old sources are kept.
STAMP_FLAG=()
[[ "${IGNORE_STAMP:-0}" == 1 ]] && STAMP_FLAG=(--ignore-stamp)
( cd "$APP" && REX_MAX_JUMP_TABLE_ENTRIES=1024 REX_REGISTER_SHARD_SPAN_BYTES=262144 \
    "$REXGLUE" codegen "$MANIFEST_NAME" "${STAMP_FLAG[@]}" ) 2>&1 | tee "$ROOT/out/codegen.log"

[[ -d "$GEN" ]] || { echo "error: the generator produced no $GEN" >&2; exit 1; }
echo "done: $GEN"
