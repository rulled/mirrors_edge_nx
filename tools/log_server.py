#!/usr/bin/env python3
"""Receives the live log stream of the NRO over TCP (the log_network cvar).

On the console the app connects once at startup and sends every log line plus
stdout/stderr (NVK messages) to this listener. Nothing blocks the game: a slow
or absent reader means dropped lines, never a stall.

    python tools/log_server.py                 # 0.0.0.0:28771, one file per run
    python tools/log_server.py --port 28771
    python tools/log_server.py --out out/switch_logs/live.log

Then, on the SD card, set in mirrorsedge.toml:

    log_network = "<PC IPv4>:28771"

and launch the game through title takeover (hold R on an installed title).
Windows: allow inbound TCP on the port for the private network, e.g. as admin

    netsh advfirewall firewall add rule name="MirrorsEdgeNX log" dir=in ^
          action=allow protocol=TCP localport=28771

The tool keeps listening after the game exits, so the next launch lands in a new
file in the same folder.
"""
import argparse
import os
import socket
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_ipv4s():
    """Best-effort list of this machine's IPv4 addresses (to print as a hint)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 9))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=28771)
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "switch_logs"))
    ap.add_argument("--quiet", action="store_true", help="write only the file")
    args = ap.parse_args()

    if args.out.lower().endswith(".log"):
        out_dir = os.path.dirname(args.out) or "."
        fixed_file = args.out
    else:
        out_dir = args.out
        fixed_file = None
    os.makedirs(out_dir, exist_ok=True)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.bind, args.port))
    srv.listen(1)
    ips = local_ipv4s()
    print(f"listening on {args.bind}:{args.port}")
    print("put this in mirrorsedge.toml on the SD card:")
    for ip in ips or ["<this PC>"]:
        print(f'    log_network = "{ip}:{args.port}"')
    print("waiting for the console...")

    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = fixed_file or os.path.join(out_dir, f"live_{stamp}.log")
        print(f"\n== {time.strftime('%H:%M:%S')} connected from {addr[0]}:{addr[1]} -> {path}")
        total = 0
        try:
            with open(path, "wb") as fh:
                pending = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    fh.flush()
                    total += len(chunk)
                    if not args.quiet:
                        pending += chunk
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            sys.stdout.write(line.decode("utf-8", "replace") + "\n")
                        sys.stdout.flush()
        except (ConnectionResetError, OSError):
            pass
        finally:
            conn.close()
        print(f"== disconnected, {total} bytes in {path}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
