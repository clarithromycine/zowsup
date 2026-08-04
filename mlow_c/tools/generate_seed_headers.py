#!/usr/bin/env python3
"""
generate_seed_headers.py — Convert .bin seed files into C header arrays
for embedding into the mlow_c shared library.

Usage: python3 generate_seed_headers.py
"""

import os, sys

SEEDS = [
    ("../data/pitch_seed.bin", "pitch_seed_data", "pitch_seed_data.h"),
    ("../data/cc_seed.bin",    "cc_seed_data",    "cc_seed_data.h"),
    ("../data/lsf_seed.bin",   "lsf_seed_data",   "lsf_seed_data.h"),
]

def generate(bin_path, var_name, out_path):
    with open(bin_path, "rb") as f:
        data = f.read()

    lines = []
    lines.append(f"/* Auto-generated from {os.path.basename(bin_path)} — do not edit. */")
    lines.append(f"#ifndef {var_name.upper()}_H")
    lines.append(f"#define {var_name.upper()}_H")
    lines.append("")
    lines.append(f"static const unsigned char {var_name}[{len(data)}] = {{")
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_vals = ", ".join(f"0x{b:02x}" for b in chunk)
        lines.append(f"    {hex_vals},")
    # Remove trailing comma on last data line
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("};")
    lines.append(f"static const int {var_name}_len = {len(data)};")
    lines.append("")
    lines.append(f"#endif /* {var_name.upper()}_H */")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Generated {out_path} ({len(data)} bytes)")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for bin_rel, var_name, out_name in SEEDS:
        bin_path = os.path.join(script_dir, bin_rel)
        out_path = os.path.join(script_dir, out_name)
        generate(bin_path, var_name, out_path)

if __name__ == "__main__":
    main()