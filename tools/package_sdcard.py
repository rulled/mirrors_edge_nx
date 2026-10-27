#!/usr/bin/env python3
"""Packages the release bundle for Nintendo Switch SD card:

  out/release/switch/mirrorsedge-nx/
    ├── mirrorsedge.nro
    ├── mirrorsedge.toml
    ├── mirrorsedge_shaders.mesp
    ├── mirrorsedge_shaders.mesp.idx
    └── game_root/ (TdGame, default.xex)
"""

import os
import shutil
import sys

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    release_dir = os.path.join(root, "out", "release", "switch", "mirrorsedge-nx")
    os.makedirs(release_dir, exist_ok=True)

    # 1. NRO
    nro_src = os.path.join(root, "out", "build", "switch_app", "mirrorsedge.nro")
    if not os.path.isfile(nro_src):
        sys.exit(f"mirrorsedge.nro not found at {nro_src}")
    shutil.copy2(nro_src, os.path.join(release_dir, "mirrorsedge.nro"))
    print(f"Copied mirrorsedge.nro ({os.path.getsize(nro_src) / (1024*1024):.2f} MB)")

    # 2. Config
    toml_src = os.path.join(root, "app", "mirrorsedge.toml")
    shutil.copy2(toml_src, os.path.join(release_dir, "mirrorsedge.toml"))
    print("Copied mirrorsedge.toml")

    # 3. Shaders
    mesp_src = os.path.join(root, "out", "shaderlib", "mirrorsedge_shaders.mesp")
    idx_src = os.path.join(root, "out", "shaderlib", "mirrorsedge_shaders.mesp.idx")
    if not os.path.isfile(mesp_src) or not os.path.isfile(idx_src):
        sys.exit("Shader library not found in out/shaderlib/")
    shutil.copy2(mesp_src, os.path.join(release_dir, "mirrorsedge_shaders.mesp"))
    shutil.copy2(idx_src, os.path.join(release_dir, "mirrorsedge_shaders.mesp.idx"))
    print("Copied mirrorsedge_shaders.mesp & idx")

    # 4. Instructions
    install_txt = os.path.join(release_dir, "INSTALL.txt")
    with open(install_txt, "w", encoding="utf-8") as f:
        f.write("""Mirror's Edge NX (Native Nintendo Switch Static Recompilation)
==============================================================

How to Install on Nintendo Switch:
----------------------------------
1. Copy the entire 'switch' folder to your SD card root (sdmc:/).
   The path on the SD card must be:
     sdmc:/switch/mirrorsedge-nx/
       ├── mirrorsedge.nro
       ├── mirrorsedge.toml
       ├── mirrorsedge_shaders.mesp
       ├── mirrorsedge_shaders.mesp.idx
       └── game_root/
             ├── default.xex
             └── TdGame/

2. Launching:
   - Use TITLE TAKEOVER mode: Hold [R] while launching any installed Switch game.
   - Or install a 39-bit address space forwarder generated via Sphaira.
   - DO NOT run in Album applet mode (applet mode is restricted to ~400 MB RAM).

Target Performance:
-------------------
- 30-60 FPS on stock clocks.
- Dynamic Resolution Scaling (540p handheld, up to 1080p docked).
- AMD FidelityFX CAS sharpening enabled by default.
""")
    print("Wrote INSTALL.txt")

    print(f"\nSD Card package ready in: {release_dir}")

if __name__ == "__main__":
    main()
