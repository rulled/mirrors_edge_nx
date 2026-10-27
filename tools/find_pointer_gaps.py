#!/usr/bin/env python3
"""Finds function pointers stored in the guest image that point into code gaps.

The runtime dies with "Call to invalid or unregistered function at guest address X"
when an indirect call (vtable slot, callback, function pointer) targets an address
that the codegen never marked as a function start. tools/find_gaps.py lists those
gaps but the game only reveals them one call at a time.

This tool takes the opposite direction: it reads the image's data and looks for
32-bit words that hold an address inside a gap, so all vtable slots of that kind
are known before booting. Candidates at the exact start of a gap are the ones a
codegen entry can turn into a function; values in the middle of a gap are
middle-entry calls and are reported separately.

Usage:
    python3 tools/find_pointer_gaps.py [--xex assets/game_root/default.xex] [--min 8]
    python3 tools/find_pointer_gaps.py --toml out/pointer_gaps/candidates.toml
"""
import argparse
import bisect
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_xex_sections(path):
    """Returns [(name, va, size, data)] for every PE section of an XEX2 image."""
    with open(path, "rb") as fh:
        head = fh.read(24)
        magic, _mod_flags, pe_off, _sec, _cert, _opt = struct.unpack(">4sIIIII", head)
        if magic != b"XEX2":
            raise SystemExit(f"{path}: not an XEX2 file")
        fh.seek(pe_off)
        pe = fh.read(24)
        if pe[:4] != b"PE\0\0":
            raise SystemExit(
                f"{path}: the PE image at 0x{pe_off:X} is encrypted or compressed. "
                "ReXGlue's loader decrypts it; this scanner needs a decrypted/default.xex "
                "(or a dumped PE image), so it cannot run on the retail container directly.")
        nsec = struct.unpack("<H", pe[6:8])[0]
        opt_size = struct.unpack("<H", pe[20:22])[0]
        fh.seek(pe_off + 24 + opt_size)
        headers = []
        for _ in range(nsec):
            raw = fh.read(40)
            if len(raw) != 40:
                raise SystemExit(f"{path}: truncated PE section table")
            name = raw[:8].rstrip(b"\0").decode("ascii", "replace")
            vsize, va, rawsize, rawptr = struct.unpack("<IIII", raw[8:24])
            headers.append((name, va, max(vsize, rawsize), rawptr))
        # Read the data after all headers are consumed. Seeking back to
        # header (len(secs) + 1) skipped the second section: len(secs) had
        # already been incremented by the append.
        secs = []
        for name, va, size, rawptr in headers:
            fh.seek(rawptr)
            data = fh.read(size)
            if len(data) != size:
                raise SystemExit(f"{path}: section {name} extends past end of file")
            secs.append((name, va, size, data))
    return secs


def load_gaps(gen_dir, func_starts):
    """Gap starts and ranges: a gap is [end of one function, start of the next)."""
    sizes = {}
    import glob
    import re
    for path in glob.glob(os.path.join(gen_dir, "*recomp*.cpp")):
        cur = None
        n = 0
        with open(path, errors="replace") as fh:
            for line in fh:
                m = re.match(r"DEFINE_REX_FUNC\(sub_([0-9A-F]+)\)", line)
                if m:
                    if cur is not None:
                        sizes[cur] = n
                    cur = int(m.group(1), 16)
                    n = 0
                    continue
                if cur is None:
                    continue
                if line.startswith("}"):
                    sizes[cur] = n
                    cur = None
                    continue
                if re.match(r"\t// \S", line):
                    n += 1
    gaps = []
    for i, a in enumerate(func_starts[:-1]):
        n = sizes.get(a)
        if n is None:
            continue
        end = a + 4 * n
        if end < func_starts[i + 1]:
            gaps.append((end, func_starts[i + 1]))
    return gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xex", default=os.path.join(ROOT, "assets", "game_root", "default.xex"))
    ap.add_argument("--gen", default=os.path.join(ROOT, "app", "generated", "default"))
    ap.add_argument("--min", type=int, default=8, help="ignore gaps smaller than this (default 8)")
    ap.add_argument("--toml", default=os.path.join(ROOT, "out", "pointer_gaps", "candidates.toml"))
    args = ap.parse_args()

    with open(os.path.join(args.gen, "codegen.partition.json")) as fh:
        starts = sorted(int(k, 16) for k in json.load(fh)["assignments"])
    print(f"functions: {len(starts)}")

    gaps = [(s, e, e - s) for s, e in load_gaps(args.gen, starts) if e - s >= args.min]
    gap_starts = {s: (e, n) for s, e, n in gaps}
    print(f"gaps >= {args.min} bytes: {len(gaps)}")

    secs = read_xex_sections(args.xex)
    code_lo, code_hi = 0x82230000, 0x82EC6BCC
    by_start = {}
    by_inside = {}
    for name, va, _size, data in secs:
        for off in range(0, len(data) - 3, 4):
            v = struct.unpack_from(">I", data, off)[0]
            if not (code_lo <= v < code_hi) or v & 3:
                continue
            after = bisect.bisect_right(starts, v)
            if after and starts[after - 1] == v:
                continue  # a real function start
            if v in gap_starts:
                by_start.setdefault(v, []).append(va + off)
            else:
                for s, e, n in gaps:
                    if s < v < e:
                        by_inside.setdefault(v, []).append(va + off)
                        break

    print(f"\ndata words pointing at a GAP START: {len(by_start)}")
    for v in sorted(by_start):
        e, n = gap_starts[v]
        print(f"  0x{v:08X}  gap {n:4d} bytes  referenced from {', '.join('0x%08X' % r for r in by_start[v][:4])}"
              f"{' +%d' % (len(by_start[v]) - 4) if len(by_start[v]) > 4 else ''}")
    print(f"\ndata words pointing INSIDE a gap (middle entry): {len(by_inside)}")
    for v in sorted(by_inside)[:40]:
        print(f"  0x{v:08X}  referenced from {', '.join('0x%08X' % r for r in by_inside[v][:3])}")
    if len(by_inside) > 40:
        print(f"  ... and {len(by_inside) - 40} more")

    os.makedirs(os.path.dirname(args.toml) or ".", exist_ok=True)
    with open(args.toml, "w") as fh:
        fh.write("# Function pointers found in the guest image that land in code gaps.\n")
        fh.write("# Generated by tools/find_pointer_gaps.py; review with tools/gap_classify.py.\n[functions]\n")
        for v in sorted(by_start):
            fh.write(f'"{v:#010X}" = {{ }}  # gap of {gap_starts[v][1]} bytes\n')
    print(f"\nTOML: {args.toml}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
