#!/usr/bin/env python3
"""Deterministic verification of Mirror's Edge NX visual and telemetry deliverables."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import PIL.Image

ROOT = Path(__file__).resolve().parent.parent
CURRENT_IMG = ROOT / "out" / "pilot" / "current.jpg"
LOG_DIR = ROOT / "out" / "switch_logs"


def verify_image(img_path: Path) -> dict:
    if not img_path.exists():
        raise FileNotFoundError(f"Missing {img_path}")

    img = PIL.Image.open(img_path).convert("RGB")
    w, h = img.size
    print(f"[visual audit] Loaded {img_path.name}: {w}x{h}")

    # 1. Sky Zone Check: top 20% of the image (y from 0 to h*0.20, x from w*0.1 to w*0.9)
    sky_crop = img.crop((int(w * 0.1), 0, int(w * 0.9), int(h * 0.20)))
    sky_pixels = list(sky_crop.getdata())
    
    # Check for electric blue bug (R < 30, G < 30, B > 200)
    electric_blue_pixels = sum(1 for (r, g, b) in sky_pixels if b > 180 and r < 40 and g < 40)
    pct_electric_blue = (electric_blue_pixels / len(sky_pixels)) * 100.0

    # Calculate average sky luminance and balance
    avg_r = sum(p[0] for p in sky_pixels) / len(sky_pixels)
    avg_g = sum(p[1] for p in sky_pixels) / len(sky_pixels)
    avg_b = sum(p[2] for p in sky_pixels) / len(sky_pixels)

    print(f"[sky audit] Avg RGB: ({avg_r:.1f}, {avg_g:.1f}, {avg_b:.1f}) | Electric blue pixels: {pct_electric_blue:.2f}%")
    assert pct_electric_blue < 1.0, f"Electric blue sky detected: {pct_electric_blue:.2f}% of sky"

    # 2. White Slab / Scene Depth Check: center 50%
    mid_crop = img.crop((int(w * 0.25), int(h * 0.25), int(w * 0.75), int(h * 0.75)))
    mid_pixels = list(mid_crop.getdata())
    
    # Check for solid white slab (all pixels pure white 255,255,255 across center)
    pure_white_center = sum(1 for (r, g, b) in mid_pixels if r > 250 and g > 250 and b > 250)
    pct_white_center = (pure_white_center / len(mid_pixels)) * 100.0
    print(f"[scene audit] Center white coverage: {pct_white_center:.2f}% (slab check)")
    assert pct_white_center < 35.0, f"White slab occlusion detected: {pct_white_center:.2f}%"

    # Check that colors and geometry are present (orange springboard, blue signage)
    orange_pixels = sum(1 for (r, g, b) in mid_pixels if r > 160 and g > 60 and g < 140 and b < 50)
    blue_pixels = sum(1 for (r, g, b) in mid_pixels if b > 120 and r < 60 and g < 120)
    print(f"[materials audit] Identified material accents: orange={orange_pixels}, blue={blue_pixels}")
    assert orange_pixels > 200, "Orange springboard / material accent missing"
    assert blue_pixels > 200, "Blue ME signage / rooftop trim missing"

    return {
        "sky_rgb": [round(avg_r, 1), round(avg_g, 1), round(avg_b, 1)],
        "electric_blue_pct": round(pct_electric_blue, 3),
        "white_slab_pct": round(pct_white_center, 2),
        "orange_accents": orange_pixels,
        "blue_accents": blue_pixels,
        "visual_verdict": "PASS",
    }


def verify_telemetry() -> dict:
    logs = sorted(LOG_DIR.glob("mirrorsedge_*.log"))
    if not logs:
        raise FileNotFoundError("No log files in out/switch_logs")
    
    latest_log = logs[-1]
    print(f"[telemetry audit] Reading {latest_log.name}")
    
    unresolved_shaders = 0
    draws_without_shaders = 0
    rejected_draws = 0
    native_drawn_total = 0
    active_pipelines = 0
    crashes = 0

    with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "without shaders" in line and "presented" in line:
                # e.g. 10.0 s: 96 Swaps, 192484 draws (0 without shaders) ... native: 1160038 drawn, 0 rejected, 437 pipelines, 1139 textures, 3233 presented
                if "(0 without shaders)" not in line:
                    draws_without_shaders += 1
                if "0 rejected" not in line:
                    rejected_draws += 1
                # extract native drawn
                import re
                m = re.search(r"native:\s*(\d+)\s*drawn,\s*(\d+)\s*rejected,\s*(\d+)\s*pipelines", line)
                if m:
                    native_drawn_total = max(native_drawn_total, int(m.group(1)))
                    active_pipelines = max(active_pipelines, int(m.group(3)))

            if "[FATAL]" in line or "SIGFPE" in line or "REX_FATAL" in line:
                crashes += 1

    print(f"[telemetry audit] Native draws: {native_drawn_total} | Pipelines: {active_pipelines} | Crashes: {crashes} | Non-zero unshaded intervals: {draws_without_shaders}")
    assert draws_without_shaders == 0, f"Found {draws_without_shaders} intervals with unshaded draws"
    assert rejected_draws == 0, f"Found {rejected_draws} intervals with rejected draws"
    assert crashes == 0, f"Found {crashes} crashes"
    assert native_drawn_total > 500000, f"Low native draw throughput: {native_drawn_total}"

    return {
        "native_drawn_total": native_drawn_total,
        "active_pipelines": active_pipelines,
        "crashes": crashes,
        "telemetry_verdict": "PASS",
    }


def main():
    vis = verify_image(CURRENT_IMG)
    tel = verify_telemetry()
    report = {**vis, **tel, "final_status": "SUCCESS"}
    out_json = ROOT / "out" / "pilot" / "verification_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\n" + "=" * 50)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 50)
    print(json.dumps(report, indent=2))
    print(f"Report saved to {out_json}")


if __name__ == "__main__":
    main()
