#!/usr/bin/env python3
"""List warp destinations: per area, per sub, the event ids a map load can start (the `MAP=` of warp.lua).

  scenes.py ISO [AREA...]      (AREA in hex; default: every area with an event block)

Event block header entry 3 (3 bytes at +9: bank delta, lo, hi) = table of u16 per sub -> list of u16 object
pointers up to 0 -> per object, 3-byte entries (event id, u16 script pointer) up to an id of 0 (6F:$7956 / $7977).
Every pointer is a plain 16-bit offset from the header entry's bank (delta * 0x2000), as 69:$4822 maps it.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import extract


def u16(b, o):
    return b[o] | b[o + 1] << 8


def events(iso, area):
    """{sub: sorted event ids} for one area, or None if it has no event block."""
    base = (area * 128 + 2) * 2048
    blk = iso[base:base + 128 * 2048]
    if not re.match(extract.SIG, blk, re.S):
        return None
    d, lo, hi = blk[9:12]
    root = d * 0x2000
    table = root + (lo | hi << 8)
    out = {}
    for sub in range(0x40):
        p = root + u16(blk, table + 2 * sub)
        if p >= len(blk) - 2:
            break
        ids, i = set(), 0
        while i < 64 and u16(blk, p + 2 * i):
            o = root + u16(blk, p + 2 * i)
            j = 0
            while o + j < len(blk) and blk[o + j] and j < 3 * 64:
                ids.add(blk[o + j])
                j += 3
            i += 1
        if ids:
            out[sub] = sorted(ids)
    return out


def main():
    iso = open(sys.argv[1], 'rb').read()
    areas = [int(a, 16) for a in sys.argv[2:]] or range(0x400)
    for a in areas:
        ev = events(iso, a)
        if ev:
            for sub, ids in ev.items():
                print('area=%02X sub=%02X events=%s' % (a, sub, ' '.join('%02X' % x for x in ids)))


if __name__ == '__main__':
    main()
