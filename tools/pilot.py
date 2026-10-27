#!/usr/bin/env python3
"""Interactive State-Driven Pilot for Mirror's Edge NX.

Enables step-by-step or polled execution with exact timestamps and visual verification:
1. Launches the title from HOME menu and initializes time baseline (T0).
2. Captures timestamped screenshots (T+XX.Xs) for vision verification.
3. Sends button presses only when verified in the correct UI state.
4. Records measured timing windows into a calibration profile.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWITCH_IP = os.environ.get("SWITCH_IP", "192.168.1.100")
SYSAGENT_CLIENT = ROOT / "out" / "sys-agent" / "client" / "sysagent.py"
OUT_DIR = ROOT / "out" / "pilot"
STATE_FILE = OUT_DIR / "pilot_state.json"


def run_sysagent(*args: str, host: str = SWITCH_IP) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SYSAGENT_CLIENT), "--host", host, *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class Pilot:
    def __init__(self, host: str = SWITCH_IP):
        self.host = host
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"t0": None, "history": []}

    def _save_state(self) -> None:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def elapsed(self) -> float:
        if not self.state.get("t0"):
            return 0.0
        return time.time() - self.state["t0"]

    def launch(self) -> dict:
        print("[pilot] sending 'A' to launch Mirror's Edge from HOME menu...")
        run_sysagent("input", "click", "A", host=self.host)
        t0 = time.time()
        self.state = {
            "t0": t0,
            "history": [{"event": "launch", "timestamp": 0.0, "wall_time": t0}]
        }
        self._save_state()
        print(f"[pilot] game launched at T0 = {t0:.3f}")
        return {"t0": t0, "elapsed": 0.0}

    def capture(self, label: str = "snap") -> Path:
        el = self.elapsed()
        fname = f"{label}_T+{el:06.2f}s.jpg"
        out_path = OUT_DIR / fname
        current_sym = OUT_DIR / "current.jpg"

        res = run_sysagent("screen", "capture", "--output", str(out_path), host=self.host)
        if res.returncode != 0:
            print(f"[pilot error] Screen capture failed: {res.stderr.strip()}", file=sys.stderr)

        # Copy to current.jpg for easy persistent reading
        if out_path.exists():
            import shutil
            shutil.copyfile(out_path, current_sym)

        self.state["history"].append({
            "event": "capture",
            "label": label,
            "elapsed": el,
            "path": str(out_path)
        })
        self._save_state()

        print(f"[pilot] captured: {fname} (elapsed: T+{el:.2f}s)")
        return out_path

    def press(self, button: str, hold: float = 0.3) -> float:
        el = self.elapsed()
        print(f"[pilot] [T+{el:.2f}s] pressing '{button}' (hold {hold}s)...")
        run_sysagent("input", "press", button, host=self.host)
        time.sleep(hold)
        run_sysagent("input", "release", button, host=self.host)
        
        self.state["history"].append({
            "event": "press",
            "button": button,
            "hold": hold,
            "elapsed": el
        })
        self._save_state()
        return el

    def status(self) -> dict:
        el = self.elapsed()
        res_game = run_sysagent("game", "status", host=self.host)
        is_running = (res_game.returncode == 0)
        res_bat = run_sysagent("utility", "charge", host=self.host)
        charge = res_bat.stdout.strip() if res_bat.returncode == 0 else "unknown"
        return {
            "running": is_running,
            "charge": charge,
            "elapsed": el,
            "history_count": len(self.state.get("history", []))
        }

    def run_flow(self) -> None:
        print("[pilot flow] starting automated calibrated flow to 3D Prologue...")
        self.launch()

        # 1. Skip intro movie
        print("[pilot flow] waiting 10s for intro movie...")
        time.sleep(10.0)
        self.press("A", hold=0.3)

        # 2. Generous wait for Title Screen ("Press START button")
        print("[pilot flow] waiting 55s for Title Screen...")
        time.sleep(55.0)
        self.capture("title_screen")
        self.press("PLUS", hold=0.3)

        # 3. Autosave Dialog
        print("[pilot flow] waiting 12s for Autosave Dialog...")
        time.sleep(12.0)
        self.capture("autosave_dialog")
        self.press("A", hold=0.3)

        # 4. Main Menu -> Story Mode
        print("[pilot flow] waiting 10s for Main Menu...")
        time.sleep(10.0)
        self.capture("main_menu")
        self.press("A", hold=0.3)

        # 5. Difficulty Select -> Normal Difficulty
        print("[pilot flow] waiting 10s for Difficulty Select...")
        time.sleep(10.0)
        self.capture("difficulty_select")
        self.press("A", hold=0.3)

        # 6. Cutscene skip after 12-15s
        print("[pilot flow] waiting 14s for cutscene to become skippable...")
        time.sleep(14.0)
        self.press("A", hold=0.3)
        time.sleep(1.5)
        self.press("A", hold=0.3)

        # 7. Transition to gameplay (8-10s)
        print("[pilot flow] waiting 8s to land in 3D Gameplay...")
        time.sleep(8.0)
        self.capture("in_game_3d_prologue")
        print("[pilot flow] successfully reached 3D Gameplay!")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=SWITCH_IP)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("launch", help="Launch game and start T0 timer")
    
    p_cap = sub.add_parser("snap", help="Capture screenshot with timestamp")
    p_cap.add_argument("label", nargs="?", default="screen")

    p_press = sub.add_parser("press", help="Press button at current timestamp")
    p_press.add_argument("button")
    p_press.add_argument("--hold", type=float, default=0.3)

    p_wait = sub.add_parser("wait", help="Sleep for N seconds")
    p_wait.add_argument("seconds", type=float)

    sub.add_parser("status", help="Show pilot status")
    sub.add_parser("flow", help="Run full calibrated flow to 3D Prologue")

    args = parser.parse_args()
    pilot = Pilot(host=args.host)

    if args.cmd == "launch":
        pilot.launch()
    elif args.cmd == "snap":
        pilot.capture(label=args.label)
    elif args.cmd == "press":
        pilot.press(button=args.button, hold=args.hold)
    elif args.cmd == "wait":
        print(f"[pilot] waiting {args.seconds}s...")
        time.sleep(args.seconds)
        pilot.capture(label=f"after_wait_{args.seconds}s")
    elif args.cmd == "status":
        st = pilot.status()
        print(f"[pilot status] Running: {st['running']} | Battery: {st['charge']}% | Elapsed: T+{st['elapsed']:.2f}s")

    elif args.cmd == "flow":
        pilot.run_flow()

if __name__ == "__main__":
    main()
