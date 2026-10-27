#!/usr/bin/env python3
"""One-command pipeline: Ingest Switch shader dumps -> Wrap -> Translate -> DXC -> Pack .mesp -> Deploy to Switch."""

from __future__ import annotations

import concurrent.futures as cf
import ftplib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWITCH_IP = os.environ.get("SWITCH_IP", "192.168.1.100")
FTP_PORT = 5000

DUMPS_DIR = ROOT / "out" / "shader_dumps"
WRAPPED_DIR = ROOT / "out" / "gameplay_wrapped"
CONTAINERS_OUT = WRAPPED_DIR / "containers"
HLSL_OUT = WRAPPED_DIR / "hlsl"
SPIRV_OUT = WRAPPED_DIR / "spirv"

FINAL_CONTAINERS = ROOT / "out" / "unique_pack_containers"
FINAL_SPIRV = ROOT / "out" / "unique_pack_spirv"
MESP_OUT = ROOT / "out" / "shaderlib" / "mirrorsedge_shaders.mesp"

WRAP_TOOL = ROOT / "shaders" / "tools" / "wrap_raw_shader.py"
DXC_EXE = ROOT / "tools" / "dxc" / "bin" / "x64" / "dxc.exe"
XENOS_HLSL = "/mnt/e/MirrorsEdge_NX/out/tools/xenos_hlsl"
COMMON_H = "/mnt/e/MirrorsEdge_NX/shaders/XenosRecomp/shader_common.h"
PACK_TOOL = "/mnt/e/MirrorsEdge_NX/out/tools/me_pack_shaders"

VS_TEMPLATE = FINAL_CONTAINERS / "vs_002_006C132181D6E196.bin"
PS_TEMPLATE = FINAL_CONTAINERS / "ps_000_00161EBECDCD52F9.bin"


def step1_pull_dumps():
    print("== Step 1: Pulling all shader dumps from Switch ==")
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        f = ftplib.FTP()
        f.connect(SWITCH_IP, FTP_PORT, timeout=10)
        f.login()
        remotes = f.nlst("/switch/mirrorsedge-nx/shader_dump")
        downloaded = 0
        for rpath in remotes:
            fname = Path(rpath).name
            lpath = DUMPS_DIR / fname
            if not lpath.exists() or lpath.stat().st_size == 0:
                with open(lpath, "wb") as lf:
                    f.retrbinary(f"RETR {rpath}", lf.write)
                downloaded += 1
        f.quit()
        print(f"Downloaded {downloaded} new dumps (Total in {DUMPS_DIR}: {len(list(DUMPS_DIR.glob('*.ucode')))} ucodes)")
    except Exception as e:
        print(f"FTP pull warning: {e} (continuing with local dumps)")


def step2_wrap_dumps() -> list[Path]:
    print("== Step 2: Wrapping raw microcode into containers ==")
    CONTAINERS_OUT.mkdir(parents=True, exist_ok=True)
    existing_hashes = {c.stem.lower() for c in FINAL_CONTAINERS.glob("*.bin")}
    
    ucodes = sorted(DUMPS_DIR.glob("*.ucode"))
    wrapped = []

    for ucode in ucodes:
        h = ucode.stem.lower().replace("ps_", "").replace("vs_", "")
        if any(h in c for c in existing_hashes):
            continue

        stage = "vs" if ucode.stem.startswith("vs_") else "ps"
        template = VS_TEMPLATE if stage == "vs" else PS_TEMPLATE
        out_bin = CONTAINERS_OUT / f"{ucode.stem}.bin"

        cmd = [sys.executable, str(WRAP_TOOL), str(ucode), str(template), str(out_bin), "--stage", stage]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            wrapped.append(out_bin)
        else:
            print(f"Error wrapping {ucode.name}: {res.stderr}")

    print(f"Wrapped {len(wrapped)} new shader containers into {CONTAINERS_OUT}")
    return wrapped


def step3_translate_hlsl():
    print("== Step 3: Translating containers to HLSL via xenos_hlsl ==")
    if HLSL_OUT.exists():
        shutil.rmtree(HLSL_OUT)
    HLSL_OUT.mkdir(parents=True, exist_ok=True)
    src_wsl = "/mnt/e/MirrorsEdge_NX/out/gameplay_wrapped/containers"
    dst_wsl = "/mnt/e/MirrorsEdge_NX/out/gameplay_wrapped/hlsl"
    
    cmd = ["wsl", "-d", "genshin-dkp", "-e", "/bin/bash", "-c",
           f"{XENOS_HLSL} {src_wsl} {dst_wsl} {COMMON_H}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"xenos_hlsl error (rc={res.returncode}): {res.stderr}")
    else:
        print(res.stdout.strip())
    hlsl_files = list(HLSL_OUT.glob("*.hlsl"))
    print(f"Total HLSL files translated: {len(hlsl_files)}")
def step4_compile_dxc():
    print("== Step 4: Compiling HLSL to SPIR-V using DXC ==")
    if SPIRV_OUT.exists():
        shutil.rmtree(SPIRV_OUT)
    SPIRV_OUT.mkdir(parents=True, exist_ok=True)
    hlsl_files = sorted(HLSL_OUT.glob("*.hlsl"))
    def compile_one(f: Path):
        stem = f.stem
        spv_out = SPIRV_OUT / f"{stem}.spv"
        is_ps = stem.startswith("ps_")
        target = "ps_6_6" if is_ps else "vs_6_6"
        cmd = [
            str(DXC_EXE),
            "-spirv",
            "-T", target,
            "-E", "main",
            "-HV", "2021",
            "-fspv-target-env=vulkan1.2",
            "-fvk-use-dx-layout",
        ]
        if not is_ps:
            cmd.append("-fvk-invert-y")
        cmd.extend(["-Fo", str(spv_out), str(f)])
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 and "oDepth" in res.stderr and is_ps:
            # Re-wrap with --depth, re-translate, and retry
            ucode = DUMPS_DIR / f"{stem}.ucode"
            if ucode.exists():
                out_bin = CONTAINERS_OUT / f"{stem}.bin"
                wrap_cmd = [sys.executable, str(WRAP_TOOL), str(ucode), str(PS_TEMPLATE), str(out_bin), "--stage", "ps", "--depth"]
                subprocess.run(wrap_cmd, check=True)
                wsl_src = f"/mnt/e/MirrorsEdge_NX/out/gameplay_wrapped/containers/{stem}.bin"
                wsl_dst = f"/mnt/e/MirrorsEdge_NX/out/gameplay_wrapped/hlsl/{stem}.hlsl"
                # Translate single
                subprocess.run(["wsl", "-d", "genshin-dkp", "-e", "/bin/bash", "-c",
                                f"mkdir -p /tmp/tr_{stem} /tmp/tr_{stem}/o && cp {wsl_src} /tmp/tr_{stem}/ && {XENOS_HLSL} /tmp/tr_{stem} /tmp/tr_{stem}/o {COMMON_H} && cp /tmp/tr_{stem}/o/{stem}.hlsl {wsl_dst} && rm -rf /tmp/tr_{stem}"], capture_output=True)
                res = subprocess.run(cmd, capture_output=True, text=True)
        return stem, res.returncode == 0, res.stderr

    success = 0
    failed = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for stem, ok, err in ex.map(compile_one, hlsl_files):
            if ok:
                success += 1
            else:
                failed += 1
                print(f"DXC compile failed for {stem}: {err}")

    print(f"DXC compilation complete: {success} succeeded, {failed} failed")


def step5_integrate_and_pack():
    import hashlib
    print("== Step 5: Integrating and packing mirrorsedge_shaders.mesp ==")
    # Pre-hash all existing final containers so we never insert duplicates with differing translations
    existing_hashes = {}
    for c in sorted(FINAL_CONTAINERS.glob("*.bin")):
        h = hashlib.sha256(c.read_bytes()).hexdigest()
        existing_hashes[h] = c

    spv_files = list(SPIRV_OUT.glob("*.spv"))
    added = 0
    skipped_dup = 0
    for spv in spv_files:
        stem = spv.stem
        bin_file = CONTAINERS_OUT / f"{stem}.bin"
        if not bin_file.exists():
            continue
        data = bin_file.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        if h in existing_hashes:
            skipped_dup += 1
            continue
        shutil.copyfile(bin_file, FINAL_CONTAINERS / f"{stem}.bin")
        shutil.copyfile(spv, FINAL_SPIRV / f"{stem}.spv")
        existing_hashes[h] = FINAL_CONTAINERS / f"{stem}.bin"
        added += 1

    # Remove existing package and index if they exist
    if MESP_OUT.exists():
        MESP_OUT.unlink()
    idx_out = MESP_OUT.with_suffix(".mesp.idx")
    if idx_out.exists():
        idx_out.unlink()

    total_containers = len(list(FINAL_CONTAINERS.glob("*.bin")))
    total_spirv = len(list(FINAL_SPIRV.glob("*.spv")))
    print(f"Added {added} genuinely new shaders ({skipped_dup} duplicates skipped). Total: {total_containers} unique containers, {total_spirv} SPIR-V files.")

    # Re-pack using me_pack_shaders in WSL
    wsl_containers = "/mnt/e/MirrorsEdge_NX/out/unique_pack_containers"
    wsl_spirv = "/mnt/e/MirrorsEdge_NX/out/unique_pack_spirv"
    wsl_out = "/mnt/e/MirrorsEdge_NX/out/shaderlib/mirrorsedge_shaders.mesp"

    cmd = ["wsl", "-d", "genshin-dkp", "-e", "/bin/bash", "-c",
           f"{PACK_TOOL} {wsl_containers} {wsl_spirv} {wsl_out}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("Pack stderr:", res.stderr)

    idx_out = MESP_OUT.with_suffix(".mesp.idx")
    print(f"Package created: {MESP_OUT} ({MESP_OUT.stat().st_size} bytes)")
    if idx_out.exists():
        print(f"Index created: {idx_out} ({idx_out.stat().st_size} bytes)")


def step6_deploy():
    print("== Step 6: Deploying updated .mesp package to Switch over FTP ==")
    from switch_runner import SwitchRunner
    runner = SwitchRunner(host=SWITCH_IP)
    if runner.is_game_running():
        print("Terminating game before uploading shader package...")
        runner.terminate_game()
        time.sleep(1.0)
    f = ftplib.FTP()
    f.connect(SWITCH_IP, FTP_PORT, timeout=30)
    f.login()
    
    idx_out = MESP_OUT.with_suffix(".mesp.idx")
    for local_p, remote_name in [(MESP_OUT, "mirrorsedge_shaders.mesp"), (idx_out, "mirrorsedge_shaders.mesp.idx")]:
        if local_p.exists():
            print(f"Uploading {local_p.name} ({local_p.stat().st_size} bytes)...")
            with open(local_p, "rb") as fh:
                f.storbinary(f"STOR /switch/mirrorsedge-nx/{remote_name}", fh)

    f.quit()
    print("Successfully deployed new shader package to Nintendo Switch!")


def main():
    step1_pull_dumps()
    wrapped = step2_wrap_dumps()
    if not wrapped:
        print("No new shaders needed wrapping.")
    step3_translate_hlsl()
    step4_compile_dxc()
    step5_integrate_and_pack()
    step6_deploy()


if __name__ == "__main__":
    main()
