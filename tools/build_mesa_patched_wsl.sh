#!/usr/bin/env bash
# Builds the Mesa/NVK Switch driver this port actually expects:
#   danfromtico/mesa-switch @ d4a00ea0 ("Mesa 26.2.3") + mesa-switch-masseffect.patch
# natively in WSL (no Docker), then merges libnak_rs.a into libvulkan.a the way
# masseffect-nx/mesa/build_mesa_docker.sh does.
#
#   wsl -d genshin-dkp -- bash /mnt/e/MirrorsEdge_NX/tools/build_mesa_patched_wsl.sh
#
# Result: out/mesa-sdk/libvulkan.a (+SOURE.txt), laid out exactly like the
# existing tools/mesa-sdk that tools/build_switch_unix.sh links against.
set -euo pipefail

ROOT=/mnt/e/MirrorsEdge_NX
PIN=d4a00ea0ab3f59afb967cc5d779e4263d237bd77
UPSTREAM=https://github.com/danfromtico/mesa-switch.git
SRC=/root/mesa-switch-patched
PATCH=$ROOT/out/mesa-patch/mesa-switch-masseffect.patch
OUT=$ROOT/out/mesa-sdk
MESA_OPT=${MESA_OPT:-2}
JOBS=${JOBS:-$(nproc)}
SPIRV_PREFIX=/opt/spirv-tools
export MESA_SWITCH_RUST_TARGET=aarch64-unknown-linux-gnu
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export CARGO_HOME=/root/.cargo RUSTUP_HOME=/root/.rustup
export PATH="/root/.cargo/bin:$PATH"
export PKG_CONFIG_PATH="$SPIRV_PREFIX/lib/pkgconfig"
export CMAKE_PREFIX_PATH="$SPIRV_PREFIX"

step() { echo; echo "=== $* ==="; date +%H:%M:%S; }

step "prerequisites"
[ -x /usr/bin/llvm-config-15 ] || { echo "run tools/build_mesa_switch_wsl.sh first (host packages)"; exit 1; }
[ -x /root/.cargo/bin/rustc ]   || { echo "run tools/build_mesa_switch_wsl.sh first (rust)"; exit 1; }
command -v meson >/dev/null || pip3 install --break-system-packages -q meson mako pyyaml packaging
[ -f "$PATCH" ] || { echo "missing $PATCH"; exit 1; }

step "source @ $PIN + massa effect patch"
if [ ! -d "$SRC/.git" ]; then
  mkdir -p "$SRC" && cd "$SRC"
  git init -q
  git remote add origin "$UPSTREAM"
  git fetch -q --depth 1 origin "$PIN"
  git checkout -q FETCH_HEAD
fi
cd "$SRC"
echo "VERSION $(cat VERSION)"
if git apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "patch already applied"
else
  git apply "$PATCH"
  echo "patch applied"
fi

step "wrappers (from the patched tree), headers, POSIX stubs"
mkdir -p /usr/local/libexec
# The patch rewrites bindgen-switch-wrapper.sh; the cross file hardcodes these two paths.
install -m 755 "$SRC/bindgen-switch-wrapper.sh" /usr/local/libexec/bindgen
install -m 755 "$SRC/rustc-switch-wrapper.sh" /usr/local/libexec/rustc
install -m 644 "$SRC/bindgen-atomic-shim.h" /usr/local/libexec/bindgen-atomic-shim.h
install -m 644 "$SRC/src/nouveau/headers/nv_device_info.h" "$DEVKITPRO/portlibs/switch/include/"
libdir="$(/usr/bin/llvm-config-15 --libdir)"; ver="$(/usr/bin/llvm-config-15 --version)"
[ -e "$libdir/clang/$ver" ] || ln -sfn "${ver%%.*}" "$libdir/clang/$ver"
[ -e "$libdir/clang/${ver%%.*}" ] || ln -sfn "$ver" "$libdir/clang/${ver%%.*}"
if [ ! -f "$DEVKITPRO/portlibs/switch/lib/libdl.a" ]; then
  tmp="$(mktemp -d)"; echo 'void __mesa_switch_stub_lib(void) {}' > "$tmp/stub_posix.c"
  "$DEVKITA64/bin/aarch64-none-elf-gcc" -c "$tmp/stub_posix.c" -o "$tmp/stub_posix.o"
  for L in dl rt util; do "$DEVKITA64/bin/aarch64-none-elf-ar" rcs "$DEVKITPRO/portlibs/switch/lib/lib${L}.a" "$tmp/stub_posix.o"; done
  rm -rf "$tmp"
fi

step "host tools (mesa_clc, vtn_bindgen2)"
cat > "$SRC/llvm-native.txt" <<EOF
[binaries]
llvm-config = '/usr/bin/llvm-config-15'
EOF
if [ ! -x "$SRC/builddir-native/src/compiler/clc/mesa_clc" ]; then
  meson setup builddir-native --wipe --native-file "$SRC/llvm-native.txt" --buildtype=release \
    -Dvulkan-drivers= -Dgallium-drivers= -Dshader-cache=enabled -Dplatforms= \
    -Dglx=disabled -Degl=disabled -Dopengl=false -Dgles1=disabled -Dgles2=disabled \
    -Dtools=[] -Dllvm=enabled -Dmesa-clc=enabled -Dmesa-clc-bundle-headers=enabled \
    -Dprecomp-compiler=enabled -Dinstall-mesa-clc=true
  ninja -C builddir-native -j"$JOBS" src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2
fi
export PATH="$SRC/builddir-native/src/compiler/clc:$SRC/builddir-native/src/compiler/spirv:$PATH"

step "configure cross build (-O$MESA_OPT)"
if [ ! -f builddir-switch/build.ninja ]; then
  meson setup builddir-switch --wipe --cross-file switch_cross_file.txt \
    --default-library=static --prefix=/opt/devkitpro/portlibs/switch --libdir=lib \
    --buildtype=release -Doptimization="$MESA_OPT" -Db_lto=false -Db_ndebug=true \
    -Dvulkan-drivers=nouveau -Dgallium-drivers=nouveau -Dgallium-rusticl=false \
    -Dplatforms=switch -Dglx=disabled -Degl=disabled -Dopengl=false \
    -Dgles1=disabled -Dgles2=disabled -Dshared-glapi=disabled -Dshared-llvm=disabled \
    -Dmesa-clc=system -Dprecomp-compiler=system -Dcpp_rtti=false -Dvideo-codecs= \
    -Dshader-cache=enabled -Dxmlconfig=enabled -Dexpat=enabled -Dtools=[] \
    -Dnvk-build-id="$(git rev-parse --short HEAD)"
fi

step "build"
ninja -C builddir-switch -j"$JOBS" \
  src/nouveau/vulkan/libnvk.a src/nouveau/vulkan/libvulkan.a \
  src/nouveau/compiler/libnak.a src/nouveau/compiler/libnak_rs.a

step "merge libnak_rs.a into libvulkan.a (ar -M)"
cd "$SRC/builddir-switch"
rm -f libvulkan_merged.a
printf 'CREATE libvulkan_merged.a\nADDLIB src/nouveau/vulkan/libvulkan.a\nADDLIB src/nouveau/compiler/libnak_rs.a\nSAVE\nEND\n' \
  | "$DEVKITA64/bin/aarch64-none-elf-ar" -M

step "stage (meson install --destdir)"
cd "$SRC"
rm -rf "$OUT"
meson install -C builddir-switch --destdir "$OUT" --only-changed 2>/dev/null || meson install -C builddir-switch --destdir "$OUT"
SDK="$OUT/opt/devkitpro/portlibs/switch"
for pc in "$SDK"/lib/pkgconfig/*.pc; do
  sed -i 's|^prefix=.*|prefix=${pcfiledir}/../..|' "$pc"
done

step "merge into the staged libvulkan.a"
LIBDIR=$SDK/lib
mv "$SRC/builddir-switch/libvulkan_merged.a" "$LIBDIR/libvulkan.a"
sha256sum "$LIBDIR/libvulkan.a" | tee "$LIBDIR/libvulkan.a.sha256"
cat > "$OUT/SOURCE.txt" <<EOT
danfromtico/mesa-switch $PIN (Mesa $(cat "$SRC/VERSION")) + masseffect-nx mesa/mesa-switch-masseffect.patch
built natively in WSL, -Doptimization=$MESA_OPT, libvulkan.a = libvulkan.a + libnak_rs.a merged with ar -M
EOT
ls -la "$LIBDIR/libvulkan.a"
echo "done: $OUT"
