#!/usr/bin/env python3
"""Copies game assets (default.xex, TdGame) from assets/game_root to G:/switch/mirrorsedge-nx/game_root."""

import os
import shutil
import sys
import time

def copy_file_chunked(src, dst, chunk_size=16*1024*1024):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    size = os.path.getsize(src)
    copied = 0
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while True:
            buf = fsrc.read(chunk_size)
            if not buf:
                break
            fdst.write(buf)
            copied += len(buf)

def main():
    src_root = "assets/game_root"
    dst_root = "G:/switch/mirrorsedge-nx/game_root"

    if not os.path.isdir(src_root):
        sys.exit(f"Source game_root not found: {src_root}")

    print(f"Counting files in {src_root}...")
    files_to_copy = []
    total_bytes = 0

    for root, dirs, files in os.walk(src_root):
        rel_root = os.path.relpath(root, src_root)
        if rel_root.startswith("$SystemUpdate"):
            continue
        for f in files:
            src_fp = os.path.join(root, f)
            rel_fp = os.path.relpath(src_fp, src_root)
            dst_fp = os.path.join(dst_root, rel_fp)
            size = os.path.getsize(src_fp)
            files_to_copy.append((src_fp, dst_fp, size, rel_fp))
            total_bytes += size

    print(f"Total files: {len(files_to_copy)}, Total size: {total_bytes / (1024**3):.2f} GB")
    print(f"Destination: {dst_root}")

    start_time = time.time()
    copied_bytes = 0

    for i, (src_fp, dst_fp, size, rel_fp) in enumerate(files_to_copy, 1):
        mb = size / (1024 * 1024)
        if mb >= 10.0 or rel_fp == "default.xex":
            pct = (copied_bytes / total_bytes) * 100
            print(f"[{pct:5.1f}%] ({i}/{len(files_to_copy)}) Copying {rel_fp} ({mb:.1f} MB)...")

        copy_file_chunked(src_fp, dst_fp)
        copied_bytes += size

    elapsed = time.time() - start_time
    avg_speed = (copied_bytes / (1024 * 1024)) / max(elapsed, 0.001)
    print(f"\nFinished copying {len(files_to_copy)} files in {elapsed:.1f}s ({avg_speed:.2f} MB/s)!")

if __name__ == "__main__":
    main()
