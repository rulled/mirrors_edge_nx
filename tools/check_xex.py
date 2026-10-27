#!/usr/bin/env python3
"""Inspects Xbox 360 default.xex binaries: Title ID, sections, imports, entry point, security flags.

Usage:
    python tools/check_xex.py path/to/default.xex
"""

import os
import struct
import sys

def parse_xex(path):
    if not os.path.isfile(path):
        print(f"Error: file not found: {path}", file=sys.stderr)
        return False

    with open(path, "rb") as f:
        data = f.read(4096)

    if len(data) < 32 or data[:4] != b"XEX2":
        print(f"Error: {path} is not a valid XEX2 binary (magic mismatch).", file=sys.stderr)
        return False

    (magic, module_flags, header_size, reserved, sec_offset, opt_count) = struct.unpack(">4sIIIII", data[:24])

    print("=" * 60)
    print(f" Xbox 360 XEX2 Header: {os.path.basename(path)}")
    print("=" * 60)
    print(f" Magic:             {magic.decode('ascii')}")
    print(f" Module Flags:      0x{module_flags:08X}")
    print(f" Header Size:       0x{header_size:08X}")
    print(f" Reserved:          0x{reserved:08X}")
    print(f" Security Info:     0x{sec_offset:08X}")
    print(f" Optional Headers:  {opt_count}")

    with open(path, "rb") as f:
        f.seek(sec_offset)
        security = f.read(0x114)
    if len(security) >= 0x114:
        image_size = struct.unpack_from(">I", security, 0x04)[0]
        load_address = struct.unpack_from(">I", security, 0x110)[0]
        print("-" * 60)
        print(f" Load Address:      0x{load_address:08X}")
        print(f" Image Size:        0x{image_size:08X}")
    # Read Optional Header entries
    pos = 24
    for _ in range(opt_count):
        if pos + 8 > len(data):
            break
        key, val = struct.unpack(">II", data[pos:pos+8])
        pos += 8

        # Execution info (Title ID)
        if key == 0x00040006:
            with open(path, "rb") as f:
                f.seek(val)
                exec_info = f.read(24)
            if len(exec_info) >= 18:
                media_id, ver, base_ver, title_id, platform, exec_type = struct.unpack(">IIIIBB", exec_info[:18])
                print("-" * 60)
                game_name = "Mirror's Edge" if title_id == 0x45410850 else "Unknown Title"
                print(f" Title ID:          0x{title_id:08X} ({game_name})")
                print(f" Media ID:          0x{media_id:08X}")
                print(f" Version:           0x{ver:08X}")
                print(f" Base Version:      0x{base_ver:08X}")
        elif key == 0x00010100:
            print(f" Entry Point:       0x{val:08X}")
        elif key == 0x00010201:
            print(f" Image Base:        0x{val:08X}")
        elif key == 0x00040310:
            print(f" Game Ratings Off:   0x{val:08X}")
    print("=" * 60)
    print("XEX inspection completed.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_default.xex>")
        sys.exit(1)
    parse_xex(sys.argv[1])
