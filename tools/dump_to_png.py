#!/usr/bin/env python3
"""Turn a masseffect_native_dump_* raw file into PNGs (four orientations).

usage: dump_to_png.py <file.raw> [WxH]...
"""
import sys
import numpy as np
from PIL import Image


def convert(path, w, h):
    data = np.fromfile(path, dtype=np.uint8)
    if data.size % (w * h) != 0:
        print(f"{path}: {data.size} bytes is not a multiple of {w}x{h}")
        return
    bpp = data.size // (w * h)
    if bpp not in (4, 8):
        print(f"{path}: {bpp} bytes per texel, expected 4 or 8")
        return
    texels = data.reshape(h, w, bpp)
    if bpp == 4:
        rgb = texels[..., :3].astype(np.float32) / 255.0
        kind = "RGBA8"
    else:
        rgb = texels.view(np.float16).reshape(h, w, 4)[..., :3].astype(np.float32)
        kind = "RGBA16F"
    variants = {"": rgb, "_flipv": rgb[::-1], "_fliph": rgb[:, ::-1], "_rot180": rgb[::-1, ::-1]}
    for suffix, img in variants.items():
        out = np.clip(img, 0.0, 1.0) ** (1.0 / 2.2)
        Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGB").save(path.replace(".raw", suffix + ".png"))
    print(f"{path}: {kind} {w}x{h} min {rgb.min():.4f} max {rgb.max():.4f} mean {rgb.mean():.4f} "
          f"nonzero {np.count_nonzero(rgb) / rgb.size:.3f}")


args = sys.argv[1:]
default = (1280, 720)
sizes = {
    "dump_edram_2D0_3.raw": (1280, 1280),
    "dump_res_1F5F8000.raw": (1280, 720),
    "dump_res_12658000.raw": (1280, 720),
}
for path in args:
    w, h = sizes.get(path.split("/")[-1], default)
    convert(path, w, h)
