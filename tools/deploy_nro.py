#!/usr/bin/env python3
"""Copies the built NRO and its config to the console's SD card.

Two transports:

    python tools/deploy_nro.py                    # Hekate UMS drive G: (USB)
    python tools/deploy_nro.py --ftp <switch-ip>:5000
                                                  # sys-ftpd over the network (anonymous)

The NRO and the shader library are verified by SHA256 after the copy (over FTP
by size, then the file is read back for the hash when --verify-ftp-hash is given).
`--pull-logs N` downloads the newest N game logs to out/switch_logs/ instead.
"""
import argparse
import ftplib
import hashlib
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_DIR = "/switch/mirrorsedge-nx"
FILES = [
    ("out/build/switch_app/mirrorsedge.nro", "mirrorsedge.nro", True),
    ("app/mirrorsedge.toml", "mirrorsedge.toml", False),
    ("out/shaderlib/mirrorsedge_shaders.mesp", "mirrorsedge_shaders.mesp", True),
    ("out/shaderlib/mirrorsedge_shaders.mesp.idx", "mirrorsedge_shaders.mesp.idx", True),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(16 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ftp_connect(target):
    host, _, port = target.partition(":")
    f = ftplib.FTP()
    f.connect(host, int(port or 5000), timeout=30)
    f.login()
    return f


def pull_logs(f, count):
    out = os.path.join(ROOT, "out", "switch_logs")
    os.makedirs(out, exist_ok=True)
    names = []
    try:
        for name in f.nlst(f"{REMOTE_DIR}/logs"):
            base = name.rsplit("/", 1)[-1]
            if base.endswith(".log"):
                names.append((f.size(name), base))
    except ftplib.all_errors as exc:
        raise SystemExit(f"cannot list the log directory: {exc}")
    names.sort(reverse=True)
    if not names:
        print("no logs on the console")
        return
    for size, base in names[:count]:
        local = os.path.join(out, base)
        with open(local, "wb") as fh:
            f.retrbinary(f"RETR {REMOTE_DIR}/logs/{base}", fh.write)
        print(f"{base:28} {size:>10} bytes -> {local}")
    print(f"{min(count, len(names))} log(s) pulled into {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default="G:")
    ap.add_argument("--ftp", default="", help="host[:port] of sys-ftpd on the console")
    ap.add_argument("--only-nro", action="store_true")
    ap.add_argument("--pull-logs", type=int, default=0, metavar="N")
    ap.add_argument("--verify-ftp-hash", action="store_true")
    args = ap.parse_args()

    if args.ftp:
        f = ftp_connect(args.ftp)
        if args.pull_logs:
            pull_logs(f, args.pull_logs)
            f.quit()
            return
        for rel, name, verify in FILES:
            if args.only_nro and name != "mirrorsedge.nro":
                continue
            src = os.path.join(ROOT, rel)
            if not os.path.exists(src):
                print(f"skip {name}: {rel} missing")
                continue
            local_size = os.path.getsize(src)
            with open(src, "rb") as fh:
                f.storbinary(f"STOR {REMOTE_DIR}/{name}", fh, blocksize=1 << 20)
            remote_size = f.size(f"{REMOTE_DIR}/{name}")
            line = f"{name:32} {local_size:>12} bytes"
            if remote_size != local_size:
                raise SystemExit(f"{name}: size mismatch ({remote_size} on the card)")
            if verify and args.verify_ftp_hash:
                h = hashlib.sha256()
                f.retrbinary(f"RETR {REMOTE_DIR}/{name}", h.update)
                ok = h.hexdigest() == sha256(src)
                line += "  sha256 " + h.hexdigest() + ("  OK" if ok else "  MISMATCH")
                if not ok:
                    raise SystemExit(f"{name}: checksum mismatch")
            print(line)
        f.quit()
        print("deployed over FTP to", args.ftp, time.strftime("%H:%M:%S"))
        return

    dest_dir = os.path.join(args.drive + os.sep, "switch", "mirrorsedge-nx")
    if not os.path.isdir(dest_dir):
        raise SystemExit(f"{dest_dir} is not mounted (Hekate UMS, or use --ftp)")
    for rel, name, verify in FILES:
        if args.only_nro and name != "mirrorsedge.nro":
            continue
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print(f"skip {name}: {rel} missing")
            continue
        dst = os.path.join(dest_dir, name)
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            shutil.copyfileobj(fi, fo, 16 << 20)
            fo.flush()
            os.fsync(fo.fileno())
        line = f"{name:32} {os.path.getsize(src):>12} bytes"
        if verify:
            a, b = sha256(src), sha256(dst)
            line += "  sha256 " + a + ("  OK" if a == b else "  MISMATCH")
            if a != b:
                raise SystemExit(f"checksum mismatch for {name}")
        print(line)
    print("deployed to", dest_dir, time.strftime("%H:%M:%S"))


if __name__ == "__main__":
    sys.exit(main())
