#!/usr/bin/env python3
"""Xbox 360 GOD (Games On Demand / SVOD) Extractor.

Extracts all game files and folders (default.xex, TdGame, packages, etc.)
from Xbox 360 GOD multi-part Data0000..Data00xx containers.

Usage:
    python tools/extract_god.py "path/to/00007000/HEADER_FILE" -o assets/game_root
"""

import argparse
import glob
import os
import struct
import sys

BLOCK_SIZE = 0x800
BLOCKS_PER_FILE = 0x14388
BLOCKS_PER_L0_HASH = 0x198
HASHES_PER_L1_HASH = 0xA1C4
HASH_BLOCK_SIZE = 0x1000

class GodExtractor:
    def __init__(self, header_path, out_dir):
        self.header_path = header_path
        self.out_dir = out_dir
        self.data_dir = header_path + ".data"
        if not os.path.isdir(self.data_dir):
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        data_files = sorted(glob.glob(os.path.join(self.data_dir, "Data*")))
        if not data_files:
            raise FileNotFoundError(f"No Data* files found in {self.data_dir}")

        self.fps = [open(f, "rb") for f in data_files]
        print(f"Loaded {len(self.fps)} GOD data fragments.")

        # Read root directory block from volume descriptor at 0x12000
        self.fps[0].seek(0x12000)
        magic = self.fps[0].read(20)
        if magic != b"MICROSOFT*XBOX*MEDIA":
            raise ValueError(f"Invalid volume magic in Data0000: {magic}")

        self.root_block, self.root_length = struct.unpack("<II", self.fps[0].read(8))
        print(f"Volume descriptor OK. Root directory: block {self.root_block}, length {self.root_length} bytes.")

    def block_to_offset(self, block):
        file_block = block % BLOCKS_PER_FILE
        file_index = block // BLOCKS_PER_FILE

        l0_tables = (file_block // BLOCKS_PER_L0_HASH) + 1
        l1_tables = (l0_tables // HASHES_PER_L1_HASH) + 1
        offset = (l0_tables + l1_tables) * HASH_BLOCK_SIZE + file_block * BLOCK_SIZE

        return file_index, offset

    def read_data_blocks(self, start_block, total_bytes):
        remaining = total_bytes
        curr_block = start_block
        chunks = []

        while remaining > 0:
            chunk_len = min(remaining, BLOCK_SIZE)
            f_idx, addr = self.block_to_offset(curr_block)
            self.fps[f_idx].seek(addr)
            buf = self.fps[f_idx].read(chunk_len)
            if len(buf) != chunk_len:
                raise IOError(f"Unexpected EOF reading block {curr_block} from fragment {f_idx}")
            chunks.append(buf)
            remaining -= chunk_len
            curr_block += 1

        return b"".join(chunks)

    def extract_file(self, start_block, length, dest_path):
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        remaining = length
        curr_block = start_block

        with open(dest_path, "wb") as out_fp:
            while remaining > 0:
                chunk_len = min(remaining, BLOCK_SIZE)
                f_idx, addr = self.block_to_offset(curr_block)
                self.fps[f_idx].seek(addr)
                buf = self.fps[f_idx].read(chunk_len)
                if len(buf) != chunk_len:
                    raise IOError(f"Unexpected EOF reading block {curr_block} from fragment {f_idx}")
                out_fp.write(buf)
                remaining -= chunk_len
                curr_block += 1

    def parse_directory(self, dir_block, dir_length, current_path=""):
        if dir_length == 0:
            return

        dir_data = self.read_data_blocks(dir_block, dir_length)

        def walk_node(offset):
            if offset + 14 > len(dir_data):
                return

            raw = dir_data[offset:offset+14]
            if raw == b"\x00" * 14 or raw[:4] == b"\xff\xff\xff\xff":
                return

            node_l, node_r, data_block, length, attrs, name_len = struct.unpack("<HHIIBB", raw)
            name_bytes = dir_data[offset+14:offset+14+name_len]
            name = name_bytes.decode("ascii", errors="ignore")

            # Left child
            if node_l != 0 and node_l != 0xFFFF:
                walk_node(node_l * 4)

            # Process current node
            rel_path = os.path.join(current_path, name) if current_path else name
            target_path = os.path.join(self.out_dir, rel_path)
            is_dir = bool(attrs & 0x10)

            if is_dir:
                os.makedirs(target_path, exist_ok=True)
                if length > 0:
                    self.parse_directory(data_block, length, rel_path)
            else:
                mb = length / (1024 * 1024)
                if mb >= 1.0 or name == "default.xex":
                    print(f"  [{mb:6.1f} MB] {rel_path}")
                self.extract_file(data_block, length, target_path)

            # Right child
            if node_r != 0 and node_r != 0xFFFF:
                walk_node(node_r * 4)

        walk_node(0)

    def extract_all(self):
        os.makedirs(self.out_dir, exist_ok=True)
        print(f"Extracting game files to {self.out_dir}...")
        self.parse_directory(self.root_block, self.root_length, "")
        print("Extraction completed successfully!")

    def close(self):
        for fp in self.fps:
            fp.close()

def main():
    parser = argparse.ArgumentParser(description="Xbox 360 GOD Extractor")
    parser.add_argument("header", help="Path to GOD header file (in 00007000 folder)")
    parser.add_argument("-o", "--output", default="assets/game_root", help="Destination folder")
    args = parser.parse_args()

    extractor = GodExtractor(args.header, args.output)
    try:
        extractor.extract_all()
    finally:
        extractor.close()

if __name__ == "__main__":
    main()
