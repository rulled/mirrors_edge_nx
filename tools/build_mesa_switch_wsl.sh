#!/usr/bin/env bash
# Builds libvulkan.a (NVK) for Horizon OS from NaGaa95/mesa-switch (Mesa 26.2.4)
# natively in WSL, mirroring .github/workflows/build.yml without Docker.
#
#   wsl -d genshin-dkp -- bash /mnt/e/MirrorsEdge_NX/tools/build_mesa_switch_wsl.sh
#
# Output: out/mesa-26.2.4/libvulkan.a (+ the other NVK archives and headers).
set -euo pipefail

ROOT=/mnt/e/MirrorsEdge_NX
SRC=/root/mesa-switch
OUT="$ROOT/out/mesa-26.2.4"
SPIRV_PREFIX=/opt/spirv-tools
SPIRV_TAG=vulkan-sdk-1.3.290.0
export MESA_SWITCH_RUST_TARGET=aarch64-unknown-linux-gnu
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export CARGO_HOME=/root/.cargo RUSTUP_HOME=/root/.rustup
export PATH="/root/.cargo/bin:$PATH"
export PKG_CONFIG_PATH="$SPIRV_PREFIX/lib/pkgconfig"
export CMAKE_PREFIX_PATH="$SPIRV_PREFIX"

step() { echo; echo "=== $* ==="; date +%H:%M:%S; }

step "host packages"
if [ ! -e /usr/bin/llvm-config-15 ]; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config flex bison curl ca-certificates git xz-utils \
    clang libclang-dev llvm-15-dev libclang-15-dev libclang-common-15-dev \
    libclc-15-dev libllvmspirvlib-15-dev python3-pip python3-setuptools python3-wheel
fi

step "python modules"
pip3 install --break-system-packages --no-cache-dir -q meson mako pyyaml packaging

step "SPIRV-Tools $SPIRV_TAG"
if [ ! -f "$SPIRV_PREFIX/lib/libSPIRV-Tools.a" ] && [ ! -f "$SPIRV_PREFIX/lib/libSPIRV-Tools.so" ]; then
  rm -rf /tmp/SPIRV-Tools
  git clone --depth 1 --branch "$SPIRV_TAG" https://github.com/KhronosGroup/SPIRV-Tools.git /tmp/SPIRV-Tools
  git clone --depth 1 --branch "$SPIRV_TAG" https://github.com/KhronosGroup/SPIRV-Headers.git /tmp/SPIRV-Tools/external/spirv-headers
  cmake -S /tmp/SPIRV-Tools -B /tmp/SPIRV-Tools/build -G Ninja \
    -DCMAKE_INSTALL_PREFIX="$SPIRV_PREFIX" -DCMAKE_BUILD_TYPE=Release -DSPIRV_SKIP_TESTS=ON
  cmake --build /tmp/SPIRV-Tools/build -j"$(nproc)"
  cmake --install /tmp/SPIRV-Tools/build
  rm -rf /tmp/SPIRV-Tools
fi

step "rust nightly + bindgen + cbindgen"
if [ ! -x /root/.cargo/bin/rustup ]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly --profile minimal
fi
. /root/.cargo/env
rustup component add rust-src
rustup target add "$MESA_SWITCH_RUST_TARGET"
command -v bindgen >/dev/null || cargo install bindgen-cli
command -v cbindgen >/dev/null || cargo install cbindgen

step "mesa-switch source"
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 https://github.com/NaGaa95/mesa-switch.git "$SRC"
fi
cd "$SRC"
echo "VERSION $(cat VERSION)"

step "cross wrappers, headers, stubs"
mkdir -p /usr/local/libexec
install -m 755 "$SRC/bindgen-switch-wrapper.sh" /usr/local/libexec/bindgen
install -m 755 "$SRC/rustc-switch-wrapper.sh" /usr/local/libexec/rustc
install -m 644 "$SRC/bindgen-atomic-shim.h" /usr/local/libexec/bindgen-atomic-shim.h
install -m 644 "$SRC/src/nouveau/headers/nv_device_info.h" "$DEVKITPRO/portlibs/switch/include/"
libdir="$(/usr/bin/llvm-config-15 --libdir)"
ver="$(/usr/bin/llvm-config-15 --version)"
[ -e "$libdir/clang/$ver" ] || ln -sfn "${ver%%.*}" "$libdir/clang/$ver"
[ -e "$libdir/clang/${ver%%.*}" ] || ln -sfn "$ver" "$libdir/clang/${ver%%.*}"
if [ ! -f "$DEVKITPRO/portlibs/switch/lib/libdl.a" ]; then
  tmp="$(mktemp -d)"
  echo 'void __mesa_switch_stub_lib(void) {}' > "$tmp/stub_posix.c"
  "$DEVKITA64/bin/aarch64-none-elf-gcc" -c "$tmp/stub_posix.c" -o "$tmp/stub_posix.o"
  for L in dl rt util; do
    "$DEVKITA64/bin/aarch64-none-elf-ar" rcs "$DEVKITPRO/portlibs/switch/lib/lib${L}.a" "$tmp/stub_posix.o"
  done
  rm -rf "$tmp"
fi

step "host tools (mesa_clc, vtn_bindgen2)"
cat > "$SRC/llvm-native.txt" <<EOF
[binaries]
llvm-config = '/usr/bin/llvm-config-15'
EOF
if [ ! -x "$SRC/builddir-native/src/compiler/clc/mesa_clc" ]; then
  cd "$SRC"
  meson setup builddir-native --wipe --native-file "$SRC/llvm-native.txt" --buildtype=release \
    -Dvulkan-drivers= -Dgallium-drivers= -Dshader-cache=enabled -Dplatforms= \
    -Dglx=disabled -Degl=disabled -Dopengl=false -Dgles1=disabled -Dgles2=disabled \
    -Dtools=[] -Dllvm=enabled -Dmesa-clc=enabled -Dmesa-clc-bundle-headers=enabled \
    -Dprecomp-compiler=enabled -Dinstall-mesa-clc=true
  ninja -C builddir-native src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2
fi
export PATH="$SRC/builddir-native/src/compiler/clc:$SRC/builddir-native/src/compiler/spirv:$PATH"

step "configure cross build (Vulkan/NVK only)"
cd "$SRC"
if [ ! -f builddir-switch/build.ninja ]; then
  meson setup builddir-switch --wipe --cross-file switch_cross_file.txt \
    --default-library=static --prefix=/opt/devkitpro/portlibs/switch --libdir=lib \
    --buildtype=release -Doptimization=1 -Db_lto=false -Db_ndebug=true \
    -Dvulkan-drivers=nouveau -Dgallium-drivers=nouveau -Dgallium-rusticl=false \
    -Dplatforms=switch -Dglx=disabled -Degl=disabled -Dopengl=false \
    -Dgles1=disabled -Dgles2=disabled -Dshared-glapi=disabled -Dshared-llvm=disabled \
    -Dmesa-clc=system -Dprecomp-compiler=system -Dcpp_rtti=false -Dvideo-codecs= \
    -Dshader-cache=enabled -Dxmlconfig=enabled -Dexpat=enabled -Dtools=[] \
    -Dnvk-build-id="$(git rev-parse --short HEAD)"
fi

step "build archives"
ninja -C builddir-switch \
  src/nouveau/vulkan/libnvk.a \
  src/nouveau/vulkan/libvulkan.a \
  src/vulkan/util/libvulkan_util.a \
  src/compiler/nir/libnir.a \
  src/compiler/libcompiler.a \
  src/compiler/spirv/libvtn.a \
  src/util/libxmlconfig.a \
  src/nouveau/compiler/libnak.a \
  src/nouveau/compiler/libnak_rs.a \
  src/nouveau/nil/libnil.a \
  src/nouveau/nil/liblibnil_format_table.a \
  src/nouveau/mme/libnouveau_mme.a \
  src/nouveau/winsys/libnouveau_ws.a \
  src/nouveau/headers/libnvidia_headers_c.a \
  src/compiler/rust/libcompiler_c_helpers.a \
  src/util/libmesa_util.a \
  src/util/libmesa_util_simd.a \
  src/util/blake3/libblake3.a \
  src/c11/impl/libmesa_util_c11.a

step "stage output"
mkdir -p "$OUT/lib"
for f in src/nouveau/vulkan/libnvk.a src/nouveau/vulkan/libvulkan.a \
         src/vulkan/util/libvulkan_util.a src/compiler/nir/libnir.a \
         src/compiler/libcompiler.a src/compiler/spirv/libvtn.a \
         src/util/libxmlconfig.a src/nouveau/compiler/libnak.a \
         src/nouveau/compiler/libnak_rs.a src/nouveau/nil/libnil.a \
         src/nouveau/nil/liblibnil_format_table.a src/nouveau/mme/libnouveau_mme.a \
         src/nouveau/winsys/libnouveau_ws.a src/nouveau/headers/libnvidia_headers_c.a \
         src/compiler/rust/libcompiler_c_helpers.a src/util/libmesa_util.a \
         src/util/libmesa_util_simd.a src/util/blake3/libblake3.a \
         src/c11/impl/libmesa_util_c11.a; do
  cp "builddir-switch/$f" "$OUT/lib/"
done
cp builddir-switch/src/nouveau/vulkan/*.h "$OUT/lib/" 2>/dev/null || true
sha256sum "$OUT/lib/libvulkan.a" | tee "$OUT/lib/libvulkan.a.sha256"
echo "done: $OUT"
