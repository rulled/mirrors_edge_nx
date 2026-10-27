#!/usr/bin/env python3
"""Interactive gameplay test runner with sys-agent.
Follows the exact verified sequence:
Launch -> Skip Intro Movie -> Title Screen (PLUS) -> Autosave Dialog (A) -> Main Menu (A) -> Difficulty (A) -> Chapter Load -> Skip Cutscene (A) -> In-Game.
"""
import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWITCH_IP = os.environ.get("SWITCH_IP", "192.168.1.100")
SYSAGENT_CLIENT = ROOT / "out" / "sys-agent" / "client" / "sysagent.py"

def run_sysagent(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SYSAGENT_CLIENT), "--host", SWITCH_IP, *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"[sysagent error] {res.stderr.strip()}", file=sys.stderr)
        res.check_returncode()
    return res

def send_button(button: str, hold_sec: float = 0.3) -> None:
    print(f"[input] pressing '{button}' (hold {hold_sec}s)...")
    run_sysagent("input", "press", button)
    time.sleep(hold_sec)
    run_sysagent("input", "release", button)
    time.sleep(0.3)

def take_screenshot(name: str) -> Path:
    out_path = ROOT / "out" / "screenshots" / name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[screen] capturing {name}...")
    run_sysagent("screen", "capture", "--output", str(out_path))
    return out_path

def main():
    print("[init] configuring sys-agent buttonClickSleepTime to 250ms...")
    run_sysagent("config", "set", "buttonClickSleepTime", "250")

    print("[launch] sending 'A' to launch Mirrors Edge from HOME menu...")
    send_button("A", 0.3)
    time.sleep(5.0)

    # 1. Wait for Startup Movie (~10s)
    print("[step 1] waiting 10s for Startup Movie...")
    time.sleep(10.0)
    take_screenshot("phase1_movie.jpg")

    print("[step 1] skipping Startup Movie with 'A'...")
    send_button("A", 0.3)
    time.sleep(2.0)
    send_button("A", 0.3)
    time.sleep(15.0) # Wait for Title Screen

    # 2. Title Screen ("Press START button")
    take_screenshot("phase2_title.jpg")
    print("[step 2] pressing PLUS on Title Screen to open Autosave...")
    send_button("PLUS", 0.3)
    time.sleep(4.0)

    # 3. Autosave Dialog ("Press A to continue")
    take_screenshot("phase3_autosave.jpg")
    print("[step 3] confirming Autosave dialog with 'A'...")
    send_button("A", 0.3)
    time.sleep(6.0) # Transition to Main Menu

    # 4. Main Menu ("NEW GAME - STORY")
    take_screenshot("phase4_main_menu.jpg")
    print("[step 4] selecting 'NEW GAME - STORY' with 'A'...")
    send_button("A", 0.3)
    time.sleep(4.0)

    # 5. Difficulty Selection ("NORMAL")
    take_screenshot("phase5_difficulty.jpg")
    print("[step 5] selecting Normal difficulty with 'A'...")
    send_button("A", 0.3)
    time.sleep(5.0)

    # 6. Loading Chapter
    take_screenshot("phase6_loading.jpg")
    print("[step 6] waiting 22s for Chapter loading...")
    time.sleep(22.0)

    # 7. Chapter Loaded / Intro Cutscene
    take_screenshot("phase7_cutscene.jpg")
    print("[step 7] skipping cutscene with 'A'...")
    send_button("A", 0.3)
    time.sleep(2.0)
    send_button("A", 0.3)
    time.sleep(6.0)

    # 8. In-Game Gameplay
    take_screenshot("phase8_gameplay.jpg")
    time.sleep(5.0)
    take_screenshot("phase9_gameplay2.jpg")
    time.sleep(10.0)
    take_screenshot("phase10_gameplay3.jpg")
    print("[finish] test completed!")
if __name__ == "__main__":
    main()
