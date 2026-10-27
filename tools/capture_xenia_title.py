#!/usr/bin/env python3
"""Capture Xenia Title Screen ('Press START button')."""

import ctypes
import ctypes.wintypes
import subprocess
import time
from pathlib import Path
import PIL.Image

import os
ROOT = Path(__file__).resolve().parent.parent
XENIA_EXE = Path(os.environ.get("XENIA_EXE", "xenia.exe"))
GAME_XEX = ROOT / "assets" / "game_root" / "default.xex"
OUT_IMG = ROOT / "out" / "pilot" / "xenia_title.jpg"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002


def find_xenia_hwnd(target_pid: int):
    found = []

    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                found.append((hwnd, buf.value))
        return True

    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(CMPFUNC(enum_cb), 0)
    return found[0] if found else (None, None)


def send_key(hwnd, vk):
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.15)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)


def capture_window(hwnd, out_path: Path):
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = ctypes.wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        print("Invalid window size for capture")
        return False

    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbm)

    SRCCOPY = 0x00CC0020
    gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, pt.x, pt.y, SRCCOPY)

    import struct
    bmi = bytearray(40)
    struct.pack_into("<IiiHHIIIIII", bmi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = bytearray(w * h * 4)
    gdi32.GetDIBits(hdc_mem, hbm, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf), (ctypes.c_char * 40).from_buffer(bmi), 0)

    img = PIL.Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)

    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)
    print(f"Captured {w}x{h} reference frame to {out_path}")
    return True


def main():
    print(f"Launching Xenia with {GAME_XEX}...")
    proc = subprocess.Popen([str(XENIA_EXE), str(GAME_XEX)])
    hwnd = None
    for _ in range(60):
        hwnd, title = find_xenia_hwnd(proc.pid)
        if hwnd:
            print(f"Found Xenia window: '{title}' (hwnd: {hwnd}, pid: {proc.pid})")
            break
        time.sleep(0.5)

    if not hwnd:
        proc.terminate()
        sys.exit("Xenia window not found within 30s")

    # Wait for Startup Movie (10s)
    print("Waiting 10s for startup movie...")
    time.sleep(10.0)
    print("Skipping movie...")
    send_key(hwnd, VK_RETURN)
    time.sleep(1.0)
    send_key(hwnd, VK_RETURN)

    # Wait for Title Screen
    print("Waiting 30s for Title Screen ('Press START button')...")
    time.sleep(30.0)

    print("Capturing Title Screen reference...")
    capture_window(hwnd, OUT_IMG)

    time.sleep(1.0)
    proc.terminate()
    print("Xenia terminated cleanly.")


if __name__ == "__main__":
    main()
