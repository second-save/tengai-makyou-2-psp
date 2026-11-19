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

SIG = rb'\x4c.[\x60-\x7f]\x4c.[\x60-\x7f]\x4c.[\x60-\x7f]\x00'  # three JMPs into the module ($6000-$7FFF), then entry 3
MIRROR = 0x8000000  # second copy of the start of the track


def far(v):
    return (v >> 13) * 0x2000 + (v & 0x1FFF)


def expand(m, words, depth=0):
    """Replace dictionary codes (1F nn, 1-based) by their words. Byte level: a word can supply the trail byte of a kanji."""
    out, i = bytearray(), 0
    while i < len(m):
        if m[i] == 0x1F and i + 1 < len(m) and 0 < m[i + 1] <= len(words) and depth < 4:
            out += expand(words[m[i + 1] - 1], words, depth + 1)
            i += 2
        else:
            out.append(m[i])
            i += 1
    return bytes(out)


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
            i += 2 if c == 0x1B else 1  # 1B takes one raw argument byte
    return True


def block(iso, base, valid=valid):
    d, lo, hi = iso[base + 12:base + 15]
    tab = d * 0x2000 + (lo | hi << 8)  # plain 16-bit block offset, like the group offsets (no bank masking)
    offs = []
    i = 0
    while True:
        v = iso[base + tab + i * 2] | iso[base + tab + i * 2 + 1] << 8
        if iso[base + tab + i * 2:base + tab + i * 2 + 4] == b'\0\1\2\3' or v == 0xFFFF or (i >= 2 and tab + i * 2 == offs[1]):
            break  # the table ends at a 00..0F byte ramp, at FF padding, or where the dictionary starts
        if i == 256:  # the group index is one byte; a block without the ramp once kept this loop running for an hour
            print('sector', base // 2048, 'table at', hex(tab), 'has no end ramp: block skipped', file=sys.stderr)
            return {'sector': base // 2048, 'table': tab, 'groups': []}
        offs.append(v)
        i += 1
    starts = set(far(v) for v in offs[1:]) | {tab}
    for e in range(3, 7):  # the other header pointers bound the last stream
        d2, lo2, hi2 = iso[base + e * 3:base + e * 3 + 3]
        starts.add(d2 * 0x2000 + (lo2 | hi2 << 8))
    starts = sorted(starts)
    groups, words = [], []
    for g, v in enumerate(offs):
        o = far(v)
        if g > 1 and tab <= o < tab + len(offs) * 2:  # empty group parked on the table: decoding it gave junk messages
            groups.append({'offset': v, 'kind': 'lz', 'msgs': [], 'tail': ''})
            continue
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
        for k, m in enumerate(msgs):  # the bound can be far past the real end: stop at the first message that is not text
            if not valid(expand(m, words)):
                msgs = msgs[:k]
                break
        groups.append({'offset': v, 'kind': 'lz', 'msgs': [m.hex() for m in msgs], 'tail': tail.hex()})
    return {'sector': base // 2048, 'table': tab, 'groups': groups}


def main(iso_path, out_path):
    iso = open(iso_path, 'rb').read()
    blocks = [block(iso, m.start()) for m in re.finditer(SIG, iso, re.S)
              if m.start() % 2048 == 0 and m.start() < MIRROR]
    # the signature also fits modules without text: every text module carries the same 106-word dictionary
    blocks = [b for b in blocks if len(b['groups']) > 1 and len(b['groups'][1]['msgs']) == 106]
    json.dump(blocks, open(out_path, 'w'), indent=0)
    n = sum(len(g['msgs']) for b in blocks for g in b['groups'] if g['kind'] == 'lz')
    print(len(blocks), 'blocks,', n, 'messages,', sum(len(b['groups']) for b in blocks), 'groups')


if __name__ == '__main__':
    main(*sys.argv[1:])
