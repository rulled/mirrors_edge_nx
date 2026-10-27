# Mirror's Edge NX

Native static recompilation port of **Mirror's Edge (Xbox 360, Unreal Engine 3)** for the **Nintendo Switch (ARM64 Horizon OS)**.

Based on the [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk), [XenosRecomp](https://github.com/hedge-dev/XenosRecomp), and the architectural groundwork of [nfsmw-nx](https://github.com/StevensND/nfsmw-nx).

---

## Architecture Overview
- **AOT Recompilation:** PowerPC (Xenon) `default.xex` statically lifted to C++ via ReXGlue SDK.
- **Graphics Pipeline:** Custom high-throughput PM4 command ring buffer translating ATI Xenos microcode to native Vulkan (Mesa NVK / `gm20b`).
- **Shader Translation:** Microcode translated to SPIR-V via XenosRecomp with custom dynamic UBO bindings.
- **Hardware Target:** Nintendo Switch (Tegra X1 GM20B, Maxwell architecture) targeting 30 FPS at 1280x720.

---

## Build Requirements
- **OS:** Linux (or WSL 2 on Windows)
- **Toolchain:**
  - `devkitA64` and `libnx` (devkitPro)
  - CMake 3.25+, Ninja
  - Clang / LLVM 18+
  - Switch Mesa NVK portlibs (`switch-mesa`)
- **Game Assets:** Legal dump of Xbox 360 Mirror's Edge (`default.xex`, `TdGame/` content packages).

---

## Building
```bash
# Configure and build the Switch executable (.nro)
tools/build_switch.sh
```

---

## Legal
This repository contains no game assets, copyrighted binaries, or proprietary Nintendo/Microsoft code. Users must provide their own legally acquired copy of Mirror's Edge for Xbox 360.
