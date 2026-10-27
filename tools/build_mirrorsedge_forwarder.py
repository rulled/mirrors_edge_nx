import os, sys, json, pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "out/research/prototype-switch/repo/forwarder"))
import nsp_container as nc

# Title configuration
TID_HEX = "014D455845470000" # 01 + "MEXEG" + 0000
TID = int(TID_HEX, 16)
TITLE = "Mirror's Edge"
AUTHOR = "EA DICE / ReXGlue"
VERSION = "1.0.0"
NRO_PATH = "sdmc:/switch/mirrorsedge-nx/mirrorsedge.nro"
ICON_PATH = os.path.join(REPO, "app/icon.jpg")
KEYS_PATH = os.environ.get("PROD_KEYS", os.path.expanduser("~/.switch/prod.keys"))
LOADER_DIR = os.path.join(REPO, "out/forwarder_src/loader")
OUT_NSP = os.path.join(REPO, "out/MirrorsEdge_4Cores.nsp")

print(f"Building forwarder NSP for {TITLE} (TID {TID_HEX})...")

# 1. Load keys
key = nc.header_key(KEYS_PATH)
print("Loaded header_key from prod.keys!")

# 2. Read compiled 4-core loader
nso = open(os.path.join(LOADER_DIR, "hbl.nso"), "rb").read()
npdm = open(os.path.join(LOADER_DIR, "hbl.npdm"), "rb").read()
print(f"Read loader: nso={len(nso)} bytes, npdm={len(npdm)} bytes")

# 3. Read icon
icon = open(ICON_PATH, "rb").read()
assert icon[:2] == b"\xff\xd8", "Icon must be JPEG"
print(f"Read icon: {len(icon)} bytes")

# 4. Build Program NCA
program = nc.Nca(nc.CONTENT_PROGRAM, TID)
program.add_pfs0([("main", nso), ("main.npdm", npdm)], nc.EXEFS_BLOCK)
program.add_romfs([("nextArgv", NRO_PATH.encode()), ("nextNroPath", NRO_PATH.encode())])
program_data = program.build(key)
print(f"Built Program NCA: {len(program_data)} bytes")

# 5. Build Control NCA
nacp = nc.make_nacp(TID, TITLE, AUTHOR, VERSION)
control = nc.Nca(nc.CONTENT_CONTROL, TID)
control.add_romfs([("control.nacp", nacp)] + [(f"icon_{lang}.dat", icon) for lang in nc.LANGUAGES])
control_data = control.build(key)
print(f"Built Control NCA: {len(control_data)} bytes")

# 6. Build Meta NCA
meta = nc.Nca(nc.CONTENT_META, TID)
meta.add_pfs0([(f"Application_{TID:016x}.cnmt",
                nc.cnmt(TID, [(nc.NCM_PROGRAM, program_data), (nc.NCM_CONTROL, control_data)]))], nc.META_BLOCK)
meta_data = meta.build(key)
print(f"Built Meta NCA: {len(meta_data)} bytes")

# 7. Package PFS0 NSP
files = [
    (nc.sha256(program_data)[:16].hex() + ".nca", program_data),
    (nc.sha256(control_data)[:16].hex() + ".nca", control_data),
    (nc.sha256(meta_data)[:16].hex() + ".cnmt.nca", meta_data)
]
nsp_data = nc.pfs0(files)

os.makedirs(os.path.dirname(OUT_NSP), exist_ok=True)
with open(OUT_NSP, "wb") as f:
    f.write(nsp_data)

print(f"\n🎉 SUCCESS: Built {OUT_NSP} ({len(nsp_data):,} bytes)!")
