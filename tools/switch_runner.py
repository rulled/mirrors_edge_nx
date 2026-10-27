#!/usr/bin/env python3
"""Programmatic Headless Switch Debug & Telemetry Runner for Mirror's Edge NX.

Automates the entire debug cycle WITHOUT requiring vision/screenshots:
1. Connects to sys-agent (port 6000) and ftpsrv (port 5000).
2. Spawns the TCP live log receiver (port 28771).
3. Launches the game and navigates to 3D Prologue via input macros.
4. Parses live telemetry in real-time:
   - Dropped/unresolved draw calls and shader hashes
   - Ring wait sleeps and CPU load
   - EDRAM conversions and rollover events
   - SIGFPE / memory crash detection
5. Pulls dumped shaders from console SD card (/switch/mirrorsedge-nx/shader_dump/)
   and reports actionable diagnostics.
"""

from __future__ import annotations

import argparse
import ftplib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SWITCH_IP = os.environ.get("SWITCH_IP", "192.168.1.100")
SYSAGENT_CLIENT = ROOT / "out" / "sys-agent" / "client" / "sysagent.py"
LOG_PORT = 28771
FTP_PORT = 5000


class SwitchRunner:
    def __init__(self, host: str = SWITCH_IP, log_port: int = LOG_PORT):
        self.host = host
        self.log_port = log_port
        self.log_lines: list[str] = []
        self.log_thread: threading.Thread | None = None
        self.log_running = False
        self.log_sock: socket.socket | None = None

    # --- sys-agent commands ---
    def sysagent(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SYSAGENT_CLIENT), "--host", self.host, *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def is_game_running(self) -> bool:
        res = self.sysagent("game", "status")
        return res.returncode == 0

    def terminate_game(self) -> bool:
        if not self.is_game_running():
            return True
        # Try HOME -> X -> A to cleanly exit
        self.sysagent("input", "click", "HOME")
        time.sleep(1.0)
        self.sysagent("input", "click", "X")
        time.sleep(1.0)
        self.sysagent("input", "click", "A")
        time.sleep(2.0)
        return not self.is_game_running()

    def send_input(self, button: str, hold: float = 0.25, sleep_after: float = 0.3) -> None:
        self.sysagent("input", "press", button)
        time.sleep(hold)
        self.sysagent("input", "release", button)
        time.sleep(sleep_after)

    # --- Live TCP Log Server ---
    def start_log_listener(self) -> None:
        self.log_lines.clear()
        self.log_running = True

        def listen():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", self.log_port))
                s.listen(1)
                s.settimeout(2.0)
                self.log_sock = s
                while self.log_running:
                    try:
                        conn, addr = s.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    conn.settimeout(1.0)
                    buf = ""
                    with conn:
                        while self.log_running:
                            try:
                                data = conn.recv(4096)
                                if not data:
                                    break
                                buf += data.decode("utf-8", errors="replace")
                                while "\n" in buf:
                                    line, buf = buf.split("\n", 1)
                                    line = line.strip()
                                    if line:
                                        self.log_lines.append(line)
                            except socket.timeout:
                                continue
                            except Exception:
                                break
            finally:
                s.close()

        self.log_thread = threading.Thread(target=listen, daemon=True)
        self.log_thread.start()

    def stop_log_listener(self) -> None:
        self.log_running = False
        if self.log_sock:
            try:
                self.log_sock.close()
            except OSError:
                pass
        if self.log_thread:
            self.log_thread.join(timeout=3.0)

    # --- Telemetry Analysis ---
    def analyze_telemetry(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "crashes": [],
            "unresolved_shaders": {},
            "ring_wait": None,
            "edram_mode": None,
            "dropped_draw_count": 0,
            "total_lines": len(self.log_lines),
            "errors": [],
            "clocks": None,
            "swap_fps_samples": [],
            "frame_times_ms": [],
            "gpu_times_ms": [],
            "stats": {},
        }
        unresolved_section = False
        for line in self.log_lines:
            # Clocks Detection
            m_clk = re.search(r"clocks:\s*CPU\s*([\d.]+)\s*MHz,\s*GPU\s*([\d.]+)\s*MHz,\s*memory\s*([\d.]+)\s*MHz", line)
            if m_clk:
                report["clocks"] = {
                    "cpu_mhz": float(m_clk.group(1)),
                    "gpu_mhz": float(m_clk.group(2)),
                    "mem_mhz": float(m_clk.group(3)),
                }

            # 10s Swaps and Presented FPS
            m_swp = re.search(r"([\d.]+)\s*s:\s*(\d+)\s*Swaps,.*?(\d+)\s*presented", line)
            if m_swp:
                dur = float(m_swp.group(1))
                swaps = int(m_swp.group(2))
                presented = int(m_swp.group(3))
                if dur > 0:
                    report["swap_fps_samples"].append({
                        "interval_s": dur,
                        "swap_fps": round(swaps / dur, 2),
                        "present_fps": round(presented / dur, 2),
                    })

            # Frame hitch / timing
            m_frm = re.search(r"frame of ([\d.]+) ms \(GPU ([\d.]+) real", line)
            if m_frm:
                report["frame_times_ms"].append(float(m_frm.group(1)))
                report["gpu_times_ms"].append(float(m_frm.group(2)))

            # Fatal / Crash Detection
            if "[FATAL]" in line or "SIGFPE" in line or "abort" in line.lower() or "REX_FATAL" in line:
                report["crashes"].append(line)

            # Ring Wait Stats
            if "[ring_wait]" in line:
                report["ring_wait"] = line

            # Unresolved Shader Pairs
            if "[native] unresolved draw shader pairs" in line:
                unresolved_section = True
                continue
            if unresolved_section:
                m = re.match(r"\s*(\d+)x\s+\(VS=([0-9A-Fa-f]+),\s+PS=([0-9A-Fa-f]+)\)", line)
                if m:
                    count = int(m.group(1))
                    pair = f"VS={m.group(2)}_PS={m.group(3)}"
                    report["unresolved_shaders"][pair] = count
                    report["dropped_draw_count"] += count
                elif not line.startswith(" "):
                    unresolved_section = False

            # EDRAM or conversion warnings
            if "[native] EDRAM" in line or "conversion" in line.lower():
                if "error" in line.lower() or "fail" in line.lower():
                    report["errors"].append(line)

        ft = report["frame_times_ms"]
        if ft:
            import statistics
            report["stats"] = {
                "count": len(ft),
                "mean_ms": round(statistics.mean(ft), 2),
                "median_ms": round(statistics.median(ft), 2),
                "p90_ms": round(sorted(ft)[int(len(ft) * 0.9)], 2),
                "pct_gt_33ms": round(100.0 * sum(1 for x in ft if x > 33.33) / len(ft), 1),
                "pct_gt_50ms": round(100.0 * sum(1 for x in ft if x > 50.0) / len(ft), 1),
                "pct_gt_100ms": round(100.0 * sum(1 for x in ft if x > 100.0) / len(ft), 1),
                "mean_fps": round(1000.0 / statistics.mean(ft), 2) if statistics.mean(ft) > 0 else 0.0,
            }
        elif report["swap_fps_samples"]:
            avg_swap = sum(s["swap_fps"] for s in report["swap_fps_samples"]) / len(report["swap_fps_samples"])
            avg_pres = sum(s["present_fps"] for s in report["swap_fps_samples"]) / len(report["swap_fps_samples"])
            report["stats"] = {
                "avg_swap_fps": round(avg_swap, 2),
                "avg_present_fps": round(avg_pres, 2),
            }
        return report

    def save_log_capture(self, label: str) -> Path:
        out_dir = ROOT / "out" / "switch_logs"
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"runner_{label}_{timestamp}.log"
        out_path.write_text("\n".join(self.log_lines) + ("\n" if self.log_lines else ""), encoding="utf-8")
        print(f"[runner] saved {len(self.log_lines)} log lines to {out_path}")
        return out_path

    def run_automated_flow(self, target_phase: str = "gameplay") -> dict[str, Any]:
        self.start_log_listener()
        try:
            print("[runner] sending 'A' to launch title...")
            self.send_input("A", 0.3, 5.0)

            print("[runner] waiting 10s for startup movie...")
            time.sleep(10.0)
            self.send_input("A", 0.3, 2.0)
            self.send_input("A", 0.3, 12.0)

            print("[runner] skipping Title screen (PLUS)...")
            self.send_input("PLUS", 0.3, 4.0)

            print("[runner] accepting Autosave dialog (A)...")
            self.send_input("A", 0.3, 4.0)

            if target_phase != "menu":
                print("[runner] selecting Story Mode (A)...")
                self.send_input("A", 0.3, 3.0)

                print("[runner] selecting Normal Difficulty (A)...")
                self.send_input("A", 0.3, 12.0)

                print("[runner] skipping Prologue Cutscene (A)...")
                self.send_input("A", 0.3, 2.0)
                self.send_input("A", 0.3, 5.0)

                print("[runner] actively in 3D Gameplay! Sampling telemetry for 10 seconds...")
                time.sleep(10.0)
            else:
                time.sleep(3.0)
        finally:
            self.stop_log_listener()
            self.save_log_capture(target_phase)
        return self.analyze_telemetry()

    # --- FTP operations ---
    def pull_shader_dumps(self, local_dest: Path | None = None) -> list[str]:
        dest = local_dest or (ROOT / "out" / "shader_dumps")
        dest.mkdir(parents=True, exist_ok=True)

        # First get directory list
        try:
            ftp = ftplib.FTP()
            ftp.connect(self.host, FTP_PORT, timeout=15)
            ftp.login()
            items: list[str] = []
            ftp.retrlines("NLST /switch/mirrorsedge-nx/shader_dump", items.append)
            ftp.quit()
        except Exception as e:
            print(f"[FTP error] Failed to list shader dumps: {e}", file=sys.stderr)
            return []

        downloaded = []
        needed = [item for item in items if item.endswith((".ucode", ".bin", ".txt")) and not (dest / Path(item).name).exists()]
        print(f"[FTP] {len(items)} files on Switch, {len(needed)} files need downloading...")

        ftp = None
        for i, item in enumerate(needed):
            fname = Path(item).name
            local_file = dest / fname
            for attempt in range(3):
                try:
                    if ftp is None:
                        ftp = ftplib.FTP()
                        ftp.connect(self.host, FTP_PORT, timeout=15)
                        ftp.login()
                    with open(local_file, "wb") as f:
                        ftp.retrbinary(f"RETR {item}", f.write)
                    downloaded.append(fname)
                    break
                except Exception:
                    if ftp:
                        try:
                            ftp.close()
                        except Exception:
                            pass
                        ftp = None
                    time.sleep(0.5)
            if (i + 1) % 50 == 0:
                print(f"[FTP] Progress: {i + 1}/{len(needed)}...")

        if ftp:
            try:
                ftp.quit()
            except Exception:
                pass
        return downloaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=SWITCH_IP, help="Switch IP address")
    parser.add_argument("action", choices=["status", "run", "pull-shaders", "terminate", "benchmark"], default="status", nargs="?")
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds for benchmark mode")
    args = parser.parse_args()

    runner = SwitchRunner(host=args.host)

    if args.action == "status":
        running = runner.is_game_running()
        print(f"Game running: {running}")
        res = runner.sysagent("utility", "charge")
        print(f"Battery charge: {res.stdout.strip()}%")

    elif args.action == "terminate":
        print("Terminating game...")
        ok = runner.terminate_game()
        print(f"Game terminated: {ok}")

    elif args.action == "pull-shaders":
        print("Pulling shader dumps over FTP...")
        pulled = runner.pull_shader_dumps()
        print(f"Downloaded {len(pulled)} new shader dump files.")

    elif args.action == "run":
        report = runner.run_automated_flow(target_phase="gameplay")
        print("\n" + "=" * 50)
        print("TELEMETRY DIAGNOSTIC REPORT (HEADLESS)")
        print("=" * 50)
        print(f"Total log lines captured: {report['total_lines']}")
        print(f"Crashes detected: {len(report['crashes'])}")
        for c in report["crashes"]:
            print(f"  CRASH: {c}")

        if report.get("clocks"):
            clk = report["clocks"]
            print(f"Console Clocks: CPU {clk['cpu_mhz']} MHz | GPU {clk['gpu_mhz']} MHz | MEM {clk['mem_mhz']} MHz")

        if report.get("stats"):
            st = report["stats"]
            if "mean_fps" in st:
                print(f"Framerate (Frame hitch): {st['mean_fps']} FPS (Mean: {st['mean_ms']} ms, Median: {st['median_ms']} ms, P90: {st['p90_ms']} ms)")
                print(f"Frame Histogram: {st['pct_gt_33ms']}% > 33.3ms (<30 FPS) | {st['pct_gt_50ms']}% > 50ms (<20 FPS) | {st['pct_gt_100ms']}% > 100ms (hitches)")
            elif "avg_swap_fps" in st:
                print(f"Framerate: Swap {st['avg_swap_fps']} FPS | Present {st['avg_present_fps']} FPS")

        if report["ring_wait"]:
            print(f"Ring Wait Status: {report['ring_wait']}")

        print(f"Total Dropped Draw Calls: {report['dropped_draw_count']}")
        if report["unresolved_shaders"]:
            print("Unresolved Shader Pairs:")
            for pair, count in sorted(report["unresolved_shaders"].items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {count}x {pair}")

        pulled = runner.pull_shader_dumps()
        print(f"Shader dumps synchronized: {len(pulled)} new files.")

    elif args.action == "benchmark":
        print(f"Running passive telemetry benchmark for {args.duration:.1f}s...")
        runner.start_log_listener()
        try:
            time.sleep(args.duration)
        finally:
            runner.stop_log_listener()
        if not runner.log_lines:
            parser.error(
                f"received no log lines from {args.host}:{runner.log_port}; "
                "start the game with log_network pointed at this host"
            )
        runner.save_log_capture("benchmark")
        report = runner.analyze_telemetry()
        print("\n" + "=" * 50)
        print(f"BENCHMARK REPORT ({args.duration:.1f}s Window)")
        print("=" * 50)
        if report.get("clocks"):
            clk = report["clocks"]
            print(f"Console Clocks: CPU {clk['cpu_mhz']} MHz | GPU {clk['gpu_mhz']} MHz | MEM {clk['mem_mhz']} MHz")
        if report.get("stats"):
            st = report["stats"]
            if "mean_fps" in st:
                print(f"Framerate: {st['mean_fps']} FPS (Mean {st['mean_ms']} ms, Median {st['median_ms']} ms, P90 {st['p90_ms']} ms)")
                print(f"Frame Histogram: {st['pct_gt_33ms']}% > 33.3ms | {st['pct_gt_50ms']}% > 50ms | {st['pct_gt_100ms']}% > 100ms")
            elif "avg_swap_fps" in st:
                print(f"Framerate: Swap {st['avg_swap_fps']} FPS | Present {st['avg_present_fps']} FPS")
        print(f"Ring Wait Status: {report['ring_wait']}")
        print(f"Crashes: {len(report['crashes'])}")
        out_file = ROOT / "out" / "pilot" / "benchmark_last.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Saved benchmark data to {out_file}")


if __name__ == "__main__":
    main()
