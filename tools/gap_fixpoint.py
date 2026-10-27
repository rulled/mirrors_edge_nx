#!/usr/bin/env python3
"""Repeat the structural gap scan until no newly exposed gap qualifies.

Each pass: find_gaps.py on the tree the previous pass produced -> gaps of 8..1024 bytes not examined
before -> scratch codegen with them declared -> gap_classify.py checks (tier 1 + no stack/LR +
no undefined-at-entry registers, and tier 2). Accepted entries are accumulated in memory; the real
app/overrides.toml is written once at the end, followed by one real codegen (tools/codegen.sh).

One codegen per pass, not two: the next pass scans the scratch tree the codegen just wrote, which is
exactly what the old version obtained by regenerating the real tree and scanning it. The scratch tree
is reused between passes, so codegen only rewrites the translation units that changed and
find_gaps.py only re-measures the files whose timestamp moved.

  python3 tools/gap_fixpoint.py SCRATCH_DIR [examined.txt ...]

SCRATCH_DIR  work folder (one subfolder per pass; it is not cleaned).
examined.txt files whose lines start with an address that must not be examined again (selected.txt of earlier
             runs).

Environment: REXGLUE = path of the rexglue host tool (default sdk/out/host/rexglue, see tools/build_host.sh).
Needs the game in assets/game_root and an existing generated tree (tools/codegen.sh).
"""
import os
import re
import subprocess
import sys
import time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = os.path.join(root, "app")
if len(sys.argv) < 2:
    sys.exit(__doc__)
scratch = os.path.abspath(sys.argv[1])
rexglue = os.path.abspath(os.environ.get("REXGLUE", os.path.join(root, "sdk", "out", "host", "rexglue")))
overrides_path = os.path.join(app, "overrides.toml")
manifest_path = os.path.join(app, "mirrorsedge_manifest.toml")
gen = os.path.join(app, "generated", "default")
work = os.path.join(scratch, "generated")
cache_path = os.path.join(scratch, "sizes.json")
evidence_path = os.path.join(scratch, "gapscan-accepted.txt")
tools = os.path.join(root, "tools")
MAX_GAP = 1024

ns = {"__name__": "gc"}
exec(compile(open(os.path.join(tools, "gap_classify.py")).read(), "gc", "exec"), ns)
examined = set()
for p in sys.argv[2:]:
    examined |= {l.split()[0] for l in open(p)}
os.makedirs(scratch, exist_ok=True)

ov = open(overrides_path).read()
m = re.search(r"^\[functions\]\s*$", ov, re.M)
if not m:
    sys.exit("app/overrides.toml has no [functions] section")
head = ov[:m.end()]
have = set(re.findall(r'"(0x[0-9A-Fa-f]+)"\s*=', ov))
base_block = "\n".join(f'"{a}" = {{ }}' for a in sorted(have, key=lambda s: int(s, 16)))

accepted_all = []  # (address, size, instructions-line)
tree = gen
t0 = time.time()
max_passes = int(os.environ.get("GAP_PASSES", "20"))
fixpoint = False


def write_overrides():
    """Writes one canonical [functions] block after every pass: a kill keeps the progress.

    The old body must not be appended: it still holds every entry that is already in
    `have`, so appending it duplicated the whole file on each pass and made the next
    codegen fail to parse the TOML.
    """
    if not accepted_all:
        return
    block = ("\n# Structural gap scan, tools/gap_fixpoint.py %s: %d entries (%d accepted this run).\n"
             % (time.strftime("%Y-%m-%d"), len(have), len(accepted_all)))
    block += "\n".join(f'"{a}" = {{ }}' for a in sorted(have, key=lambda s: int(s, 16))) + "\n"
    open(overrides_path, "w").write(head + block)


for n in range(1, max_passes + 1):
    d = os.path.join(scratch, f"pass{n}")
    os.makedirs(d, exist_ok=True)
    t_pass = time.time()

    r = subprocess.run([sys.executable, os.path.join(tools, "find_gaps.py"), "--gen", tree,
                        "--report", f"{d}/h.txt", "--toml", f"{d}/c.toml", "--cache", cache_path,
                        "--min", "8"],
                       capture_output=True, text=True)
    if r.returncode:
        print("find_gaps failed:\n" + (r.stdout + r.stderr)[-3000:])
        break
    sel = [(m.group(1), int(m.group(2))) for l in open(f"{d}/c.toml")
           for m in [re.match(r'"(0x[0-9A-F]+)" = \{ \}\s*#\s*(\d+) bytes', l)]
           if m and 8 <= int(m.group(2)) <= MAX_GAP and m.group(1) not in examined
           and m.group(1) not in have]
    examined |= {a for a, _ in sel}
    if not sel:
        print(f"pass {n}: no new gaps; fixpoint")
        break
    open(f"{d}/selected.txt", "w").write("".join(f"{a} {s}\n" for a, s in sel))

    block = base_block
    if accepted_all:
        block += "\n" + "\n".join(f'"{a}" = {{ }}' for a, _, _ in accepted_all)
    block += "\n" + "\n".join(f'"{a}" = {{ }}' for a, _ in sel)
    scratch_overrides = f"{d}/overrides.toml"
    open(scratch_overrides, "w").write(head + "\n" + block + "\n")

    # Scratch manifest: same game, the reused scratch tree, and the scratch overrides.
    man = open(manifest_path).read()
    man = re.sub(r'^game_root = .*$', f'game_root = "{root}/assets/game_root"', man, flags=re.M)
    man = re.sub(r'^file_path = .*$', f'file_path = "{root}/assets/game_root/default.xex"', man, flags=re.M)
    man = re.sub(r'^out_directory_path = .*$', f'out_directory_path = "{work}"', man, flags=re.M)
    man = re.sub(r'^includes = .*$', f'includes = ["{scratch_overrides}", "{app}/perf_overrides.toml"]', man, flags=re.M)
    open(f"{d}/manifest.toml", "w").write(man)
    env = dict(os.environ, REX_MAX_JUMP_TABLE_ENTRIES="1024", REX_REGISTER_SHARD_SPAN_BYTES="262144")
    r = subprocess.run([rexglue, "codegen", "manifest.toml"], cwd=d, capture_output=True, text=True, env=env)
    open(f"{d}/codegen.log", "w").write(r.stdout + r.stderr)
    if r.returncode:
        print(f"pass {n}: scratch codegen failed (see {d}/codegen.log)")
        print((r.stdout + r.stderr)[-1500:])
        break
    tree = work

    subprocess.run([sys.executable, os.path.join(tools, "gap_classify.py"), work, f"{d}/selected.txt",
                    f"{d}/codegen.log", f"{d}/acc.txt"], capture_output=True)
    subprocess.run([sys.executable, os.path.join(tools, "gap_classify.py"), "--tier2", work,
                    f"{d}/selected.txt", f"{d}/codegen.log", overrides_path, f"{d}/t2.txt"], capture_output=True)
    accepted = []
    for l in open(f"{d}/acc.txt").readlines() + open(f"{d}/t2.txt").readlines():
        a, s, rest = l.split(" ", 2)
        ins = [i.strip() for i in rest.lstrip("| ").strip().split(" ; ")]
        ops = [i.split()[0] for i in ins]
        if (a in have or any(re.search(r"\br1\b", i) for i in ins)
                or any(o in ("mtlr", "mflr", "ld", "std", "stwu", "lfd", "stfd") for o in ops)
                or ns["reads_undefined_at_entry"](ins)):
            continue
        accepted.append((a, int(s), l.strip()))
        have.add(a)
    print(f"pass {n}: {len(sel)} gaps, {len(accepted)} accepted "
          f"({time.time() - t_pass:.0f}s)")
    if not accepted:
        print("fixpoint")
        fixpoint = True
        break
    with open(evidence_path, "a") as ev_file:
        ev_file.writelines(l + "\n" for _, _, l in accepted)
    accepted_all.extend(accepted)
    write_overrides()

if accepted_all:
    print(f"\n{len(accepted_all)} entries in {overrides_path}")
    if fixpoint:
        print("fixpoint reached; running the real codegen once")
        b = subprocess.run(["bash", os.path.join(tools, "codegen.sh")], capture_output=True, text=True,
                           env={**os.environ, "REXGLUE": rexglue})
        if b.returncode:
            print("real codegen failed:\n" + (b.stdout + b.stderr)[-2000:])
        else:
            print((b.stdout + b.stderr).strip().splitlines()[-1])
    else:
        print(f"pass limit reached; run tools/codegen.sh and start another scan")
else:
    print("nothing accepted")

print(f"total {time.time() - t0:.0f}s")
