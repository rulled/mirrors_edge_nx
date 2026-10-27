#!/usr/bin/env python3
"""Compiles all EDRAM/utility shaders in app/src/native/mirrorsedge/shaders/ to .inc headers."""

import glob
import os
import subprocess
import sys

SPECIAL_VULKAN12 = {
    "me_edram_stencil_to_buffer",
    "me_edram_color_stencil_to_buffer",
    "me_edram_stencil_msaa2_to_buffer",
    "me_edram_depth_to_depth_msaa2",
    "me_edram_depth_msaa2_to_depth_1x",
    "me_edram_depth_to_stencil_msaa2",
    "me_edram_depth_msaa2_to_stencil_1x",
    "me_depth_resolve_guestspace_msaa2",
}

def main():
    root = "/mnt/e/MirrorsEdge_NX"
    shader_dir = os.path.join(root, "app/src/native/mirrorsedge/shaders")
    out_dir = os.path.join(shader_dir, "inc")
    os.makedirs(out_dir, exist_ok=True)

    sources = glob.glob(os.path.join(shader_dir, "*.*"))
    compiled = 0

    for s in sorted(sources):
        base = os.path.basename(s)
        name, ext = os.path.splitext(base)
        if ext not in [".comp", ".frag", ".vert"]:
            continue

        cmd = ["glslangValidator", "-V", "-x"]
        if name in SPECIAL_VULKAN12:
            cmd.extend(["--target-env", "vulkan1.2"])
            out_file = os.path.join(out_dir, f"{name}_generated.inc")
        else:
            out_file = os.path.join(out_dir, f"{name}.inc")

        cmd.extend(["-o", out_file, s])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FAILED {name}: {res.stderr}")
            sys.exit(1)
        compiled += 1

    print(f"Successfully compiled {compiled} EDRAM shaders into {out_dir}")

if __name__ == "__main__":
    main()
