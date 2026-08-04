#!/usr/bin/env python3
"""Verify/extract WARP MI tag from captured hex packets.

Usage:
  Save the hex dump (only the hex groups) to a file and run:
    python script/verify_warp_mi.py captures.txt

  To compute and compare MI, provide warp auth key (hex) and ROC:
    python script/verify_warp_mi.py captures.txt --warp-auth deadbeef... --roc 42
"""
import sys
import argparse
import re
import binascii
import hmac
import hashlib


def normalize_hex(s):
    return re.sub(r'[^0-9a-fA-F]', '', s)


def parse_hex_blocks(text):
    # extract continuous hex blocks that look like packet lines (start with 9079)
    blocks = []
    cur = ''
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if cur:
                blocks.append(cur)
                cur = ''
            continue
        # skip lines that are framing like [SEND #..] or STUN markers
        if line.startswith('[') or line.lower().startswith('stun'):
            continue
        # remove any leading non-hex words
        # find first hex char
        m = re.search(r'[0-9a-fA-F]', line)
        if not m:
            continue
        hx = normalize_hex(line)
        if not hx:
            continue
        # if starts with 9079, treat as new packet; else append
        if hx.lower().startswith('9079') and cur:
            blocks.append(cur)
            cur = hx
        else:
            cur += hx
    if cur:
        blocks.append(cur)
    return blocks


def compute_mi(warp_auth, payload_bytes, roc):
    roc_be = roc.to_bytes(4, 'big')
    mac = hmac.new(warp_auth, payload_bytes + roc_be, hashlib.sha1).digest()
    return mac[:4]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('file', nargs='?', default='-', help='File with hex dump or - for stdin')
    p.add_argument('--warp-auth', help='Warp auth key (hex) to validate MI')
    p.add_argument('--roc', type=int, help='ROC (integer) to use when validating MI')
    args = p.parse_args()

    if args.file == '-':
        text = sys.stdin.read()
    else:
        with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

    blocks = parse_hex_blocks(text)
    if not blocks:
        print('No hex packets found.')
        return

    warp_auth = None
    if args.warp_auth:
        warp_auth = binascii.unhexlify(normalize_hex(args.warp_auth))

    for i, hx in enumerate(blocks, 1):
        try:
            data = binascii.unhexlify(hx)
        except Exception as e:
            print(f'[{i}] invalid hex, skip')
            continue
        print(f'[{i}] len={len(data)} bytes')
        if len(data) < 6:
            print('  too short')
            continue
        if data[0] == 0x90 and data[1] == 0x79:
            print('  frame=0x9079')
        else:
            print('  frame=NON-9079 (starts with %02x%02x)' % (data[0], data[1]))

        if len(data) >= 4:
            mi = data[-4:]
            print('  MI (last 4):', mi.hex())
        # show head/tail snippets
        print('  head:', data[:24].hex())
        print('  tail:', data[-48:].hex())

        if warp_auth and args.roc is not None:
            calc = compute_mi(warp_auth, data[:-4], args.roc)
            print('  calc MI:', calc.hex(), 'match=', calc == mi)
        print()


if __name__ == '__main__':
    main()
