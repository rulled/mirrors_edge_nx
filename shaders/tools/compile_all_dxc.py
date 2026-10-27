#!/usr/bin/env python3
"""Compiles all generated HLSL shaders in out/hlsl to Vulkan 1.2 SPIR-V using DXC."""

import concurrent.futures
import glob
import os
import subprocess
import sys
import time

def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dxc = os.path.join(root, "tools", "dxc", "bin", "x64", "dxc.exe")
    if not os.path.isfile(dxc):
        sys.exit(f"DXC executable not found at {dxc}")

    hlsl_dir = os.path.join(root, "out", "hlsl")
    spirv_dir = os.path.join(root, "out", "spirv")
    os.makedirs(spirv_dir, exist_ok=True)

    hlsl_files = sorted(glob.glob(os.path.join(hlsl_dir, "*.hlsl")))
    if not hlsl_files:
        sys.exit(f"No .hlsl files found in {hlsl_dir}")

    print(f"Compiling {len(hlsl_files)} HLSL shaders to SPIR-V using DXC...")

    def compile_one(f):
        base = os.path.basename(f)
        stem = os.path.splitext(base)[0]
        spv_out = os.path.join(spirv_dir, f"{stem}.spv")
        err_out = os.path.join(spirv_dir, f"{stem}.err")

        is_ps = stem.startswith("ps_")
        target = "ps_6_6" if is_ps else "vs_6_6"

        cmd = [
            dxc,
            "-spirv",
            "-T", target,
            "-E", "main",
            "-HV", "2021",
            "-fspv-target-env=vulkan1.2",
            "-fvk-use-dx-layout",
        ]
        if not is_ps:
            cmd.append("-fvk-invert-y")

        cmd.extend(["-Fo", spv_out, f])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if os.path.exists(err_out):
                os.remove(err_out)
            return True, stem, None
        else:
            with open(err_out, "w", encoding="utf-8") as ef:
                ef.write(res.stderr)
            return False, stem, res.stderr

    t0 = time.time()
    success = 0
    failures = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(compile_one, f): f for f in hlsl_files}
        for fut in concurrent.futures.as_completed(futures):
            ok, stem, err = fut.result()
            if ok:
                success += 1
            else:
                failures += 1
                print(f"FAILED: {stem} -> {err.strip()[:200]}")

    elapsed = time.time() - t0
    print(f"Completed in {elapsed:.2f}s: {success} succeeded, {failures} failed.")
    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
