#!/usr/bin/env python3
"""Automated Switch runner using sys-agent and FTP.

Allows fully hands-off build, deploy, launch, monitoring, screenshots, termination,
and log retrieval.
"""
from __future__ import annotations

import argparse
import ftplib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWITCH_IP = os.environ.get("SWITCH_IP", "192.168.1.100")
FTP_PORT = int(os.environ.get("SWITCH_FTP_PORT", "5000"))
SYSAGENT_CLIENT = ROOT / "out" / "sys-agent" / "client" / "sysagent.py"


def run_sysagent(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SYSAGENT_CLIENT), "--host", SWITCH_IP, *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"[sysagent error] {res.stderr.strip()}", file=sys.stderr)
        res.check_returncode()
    return res


def ftp_connect() -> ftplib.FTP:
    f = ftplib.FTP()
    f.connect(SWITCH_IP, FTP_PORT, timeout=20)
    f.login()
    return f


def cmd_status() -> None:
    res = run_sysagent("game", "status", check=False)
    if res.returncode == 0:
        print(f"[game running] {res.stdout.strip()}")
    else:
        print(f"[game idle] {res.stderr.strip() or res.stdout.strip()}")


def cmd_screenshot(out_path: str = "out/screen_latest.jpg") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    res = run_sysagent("screen", "capture", "--output", out_path)
    print(f"[screenshot] saved {out_path}")
    return out_path


def cmd_launch() -> bool:
    # First check if game is already running
    st = run_sysagent("game", "status", check=False)
    if st.returncode == 0:
        print("[launch] game is already running")
        return True

    print("[launch] sending 'A' button to start game...")
    run_sysagent("input", "click", "A")

    # Wait up to 10s for game status to report running
    for _ in range(20):
        time.sleep(0.5)
        st = run_sysagent("game", "status", check=False)
        if st.returncode == 0:
            print(f"[launch] game started successfully: {st.stdout.strip()}")
            return True
    print("[launch] timed out waiting for game to start!", file=sys.stderr)
    return False


def cmd_terminate() -> bool:
    res = run_sysagent("game", "terminate", check=False)
    if res.returncode == 0:
        print(f"[terminate] {res.stdout.strip()}")
    else:
        print(f"[terminate] {res.stderr.strip()}")
    time.sleep(1.0)
    return True


def cmd_deploy(nro: bool = True, config: bool = True) -> None:
    f = ftp_connect()
    remote_dir = "/switch/mirrorsedge-nx"

    files_to_send = []
    if nro:
        files_to_send.append((ROOT / "out/build/switch_app/mirrorsedge.nro", "mirrorsedge.nro"))
    if config:
        files_to_send.append((ROOT / "app/mirrorsedge.toml", "mirrorsedge.toml"))

    for local_path, name in files_to_send:
        if not local_path.is_file():
            print(f"[deploy] skip {name}: {local_path} missing")
            continue
        size = local_path.stat().st_size
        print(f"[deploy] uploading {name} ({size / (1024 * 1024):.2f} MB)...")
        with open(local_path, "rb") as fh:
            f.storbinary(f"STOR {remote_dir}/{name}", fh)
        print(f"[deploy] uploaded {name} OK")
    f.quit()


def cmd_pull_logs(count: int = 1) -> list[str]:
    f = ftp_connect()
    remote_log_dir = "/switch/mirrorsedge-nx/logs"
    lines = []
    f.retrlines(f"LIST {remote_log_dir}", lines.append)

    # Parse filenames from LIST output (last token of each line)
    log_files = []
    for line in lines:
        parts = line.split()
        if parts:
            fn = parts[-1]
            if fn.endswith(".log"):
                log_files.append(fn)

    # Sort naturally by filename
    log_files.sort()
    chosen = log_files[-count:] if count > 0 else log_files

    out_dir = ROOT / "out" / "switch_logs"
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for fn in chosen:
        local_fp = out_dir / fn
        with open(local_fp, "wb") as fh:
            f.retrbinary(f"RETR {remote_log_dir}/{fn}", fh.write)
        print(f"[log] pulled {fn} ({local_fp.stat().st_size} bytes)")
        downloaded.append(str(local_fp))
    f.quit()
    return downloaded


def cmd_build() -> bool:
    print("[build] building Switch NRO via WSL...")
    res = subprocess.run(["wsl", "-d", "genshin-dkp", "--", "/mnt/e/MirrorsEdge_NX/tools/build_switch.sh"])
    return res.returncode == 0


def cmd_test_run(duration: int = 25, deploy: bool = True) -> None:
    if deploy:
        cmd_deploy()
    cmd_terminate()  # ensure clean start
    if not cmd_launch():
        return

    print(f"[test_run] waiting {duration} seconds for frame rendering...")
    step = 5
    elapsed = 0
    while elapsed < duration:
        time.sleep(step)
        elapsed += step
        if elapsed in (20, 25):
            print("[test_run] pressing PLUS (Start) button to advance to autosave...")
            run_sysagent("input", "click", "PLUS")
        elif elapsed in (30, 35, 40):
            print("[test_run] pressing 'A' button to confirm Autosave dialog...")
            run_sysagent("input", "click", "A")
        elif elapsed in (48, 52):
            print("[test_run] pressing PLUS (Start) on 'Press START button'...")
            run_sysagent("input", "click", "PLUS")
        elif elapsed in (55, 58):
            print("[test_run] pressing 'A' to enter menu...")
            run_sysagent("input", "click", "A")
        elif elapsed in (63, 66):
            print("[test_run] pressing 'A' to select Story/New Game...")
            run_sysagent("input", "click", "A")
        elif elapsed in (70, 73):
            print("[test_run] pressing 'A' to confirm difficulty...")
            run_sysagent("input", "click", "A")
        cmd_screenshot(f"out/screenshots/screen_{elapsed:02d}s.jpg")
    print("[test_run] terminating game...")
    cmd_terminate()

    print("[test_run] pulling newest log...")
    logs = cmd_pull_logs(count=1)
    if logs:
        print(f"[test_run] latest log: {logs[-1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Switch automated test tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("build")

    p_dep = sub.add_parser("deploy")
    p_dep.add_argument("--config-only", action="store_true")
    p_dep.add_argument("--nro-only", action="store_true")

    sub.add_parser("launch")
    sub.add_parser("terminate")

    p_scr = sub.add_parser("screenshot")
    p_scr.add_argument("out", nargs="?", default="out/screen_latest.jpg")

    p_log = sub.add_parser("logs")
    p_log.add_argument("-n", "--count", type=int, default=1)

    p_run = sub.add_parser("test-run")
    p_run.add_argument("-t", "--time", type=int, default=25)
    p_run.add_argument("--no-deploy", action="store_true")

    args = parser.parse_args()

    if args.cmd == "status":
        cmd_status()
    elif args.cmd == "build":
        cmd_build()
    elif args.cmd == "deploy":
        cmd_deploy(nro=not args.config_only, config=not args.nro_only)
    elif args.cmd == "launch":
        cmd_launch()
    elif args.cmd == "terminate":
        cmd_terminate()
    elif args.cmd == "screenshot":
        cmd_screenshot(args.out)
    elif args.cmd == "logs":
        cmd_pull_logs(args.count)
    elif args.cmd == "test-run":
        cmd_test_run(duration=args.time, deploy=not args.no_deploy)


if __name__ == "__main__":
    main()
