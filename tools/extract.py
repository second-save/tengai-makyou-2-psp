#!/usr/bin/env python3
"""Extract every event block's messages from the data track.

  extract.py ISO OUT.json

Block = sector-aligned module starting with SIG. Header entry 4 (3 bytes at +12: bank delta, lo, hi) points at the
message group table: u16 far offsets (>>13 = 8K bank, &0x1FFF = offset). Group 1 = dictionary (plain NUL-terminated
words); every other group = one LZ stream of NUL-terminated messages, ending where the next stream starts.
Messages are kept as hex (lossless); text decoding lives in the table codec.
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz

SIG = bytes.fromhex('4c15604c16604c1560')
MIRROR = 0x8000000  # second copy of the start of the track


def far(v):
    return (v >> 13) * 0x2000 + (v & 0x1FFF)


def valid(m):
    """True if every SJIS lead byte has a legal trail byte and no byte is in an unused range."""
    i = 0
    while i < len(m):
        c = m[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEA:
            if i + 1 >= len(m) or not (0x40 <= m[i + 1] <= 0xFC and m[i + 1] != 0x7F):
                return False
            i += 2
        elif c >= 0xEB or 0x80 == c:
            return False
        else:
            i += 1
    return True


def block(iso, base):
    d, lo, hi = iso[base + 12:base + 15]
    tab = d * 0x2000 + (lo | (hi & 0x1F) << 8)
    offs = []
    i = 0
    while True:
        v = iso[base + tab + i * 2] | iso[base + tab + i * 2 + 1] << 8
        if i >= 2 and (far(v) < far(offs[1]) or tab + i * 2 >= far(offs[1])):
            break  # the table runs up to the dictionary; smaller values after it are other data
        offs.append(v)
        i += 1
    starts = set(far(v) for v in offs[1:])
    for e in range(3, 7):  # the other header pointers bound the last stream
        d2, lo2, hi2 = iso[base + e * 3:base + e * 3 + 3]
        starts.add(d2 * 0x2000 + (lo2 | (hi2 & 0x1F) << 8))
    starts = sorted(starts)
    groups = []
    for g, v in enumerate(offs):
        o = far(v)
        if g == 0:
            groups.append({'offset': v, 'kind': 'none', 'msgs': []})
            continue
        nxt = [s for s in starts if s > o]
        if g == 1:
            end = nxt[0] if nxt else o
            raw = iso[base + o:base + end]
            words = raw.split(b'\0')[:-1] if raw.endswith(b'\0') else raw.split(b'\0')
            groups.append({'offset': v, 'kind': 'dict', 'msgs': [w.hex() for w in words]})
            continue
        if nxt:
            out, _ = lz.unpack(iso, base + o, limit=base + nxt[0])
        else:  # last stream of the block: stop at the 0xFF padding
            m = re.compile(rb'\xff{16}').search(iso, base + o)
            out, _ = lz.unpack(iso, base + o, limit=m.start() if m else base + o + 0x2000)
        msgs = out.split(b'\0')
        tail = msgs.pop()  # bytes after the last NUL: decoder slack, not a message
        if not nxt:  # unbounded stream: keep messages up to the first one that is not valid text
            for k, m in enumerate(msgs):
                if not valid(m):
                    msgs = msgs[:k]
                    break
        groups.append({'offset': v, 'kind': 'lz', 'msgs': [m.hex() for m in msgs], 'tail': tail.hex()})
    return {'sector': base // 2048, 'table': tab, 'groups': groups}


def main(iso_path, out_path):
    iso = open(iso_path, 'rb').read()
    blocks = [block(iso, m.start()) for m in re.finditer(re.escape(SIG), iso)
              if m.start() % 2048 == 0 and m.start() < MIRROR]
    json.dump(blocks, open(out_path, 'w'), indent=0)
    n = sum(len(g['msgs']) for b in blocks for g in b['groups'] if g['kind'] == 'lz')
    print(len(blocks), 'blocks,', n, 'messages,', sum(len(b['groups']) for b in blocks), 'groups')


if __name__ == '__main__':
    main(*sys.argv[1:])
