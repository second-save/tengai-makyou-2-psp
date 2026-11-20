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


BATTLE, BATTLE_ROOM = 0x40400, 0xC00   # battle lines: offset in each area's 0x40000 bytes (0xF400 of its ADPCM image), room
BATTLE_LINES = 235                      # lines in the original stream
BATTLE_CODE = 0x41000 + (0x71 - 0x69) * 0x2000 + 0x1502   # 71:$7502 LDA #hi / LDX #lo = the stream's ADPCM address


def battle(iso):
    """(messages, iso offsets of every copy) of the battle text stream: one LZ stream of NUL-terminated messages,
    the same in every area that has battles (docs/re/notes.md, "Battle text"). Follows the address in the opener,
    so it also reads a built disc where insert.py moved the stream."""
    back = 0xF400 - (iso[BATTLE_CODE + 1] << 8 | iso[BATTLE_CODE + 3])
    first = 4 * 0x40000 + BATTLE - back
    # the game picks a line by number: decode exactly BATTLE_LINES lines (trailing zeros can be padding or the last NUL)
    out, end = lz.unpack(iso, first, limit=first + BATTLE_ROOM + back,
                         stop=lambda o: o[-1:] == b'\0' and o.count(0) == BATTLE_LINES)
    msgs = out.split(b'\0')[:BATTLE_LINES]
    assert len(msgs) == BATTLE_LINES, 'battle stream: %d lines' % len(msgs)
    raw = iso[first:end]
    return msgs, [o for o in range(BATTLE - back, len(iso), 0x40000) if iso[o:o + len(raw)] == raw]


ENEMY = 0x31000   # each area's ADPCM image (= ADPCM address 0) in its 0x40000 bytes


def enemy_record(img, p):
    """One enemy record at image offset p: 21 bytes of stats, name, one byte ($F670), entries (kind, param, message)
    up to a 00, then 2 bytes ($F68A/B) that can be the next record's first two. Walked by NULs at 71:$7FA6."""
    q = img.index(0, p + 21)
    r = {'head': img[p:p + 21], 'name': img[p + 21:q], 'f670': img[q + 1], 'entries': []}
    q += 2
    while img[q]:
        e = img.index(0, q + 2)
        r['entries'].append((img[q], img[q + 1], img[q + 2:e]))
        q = e + 1
    r['tail'], r['end'] = img[q + 1:q + 3], q + 3
    return r


def enemies(iso):
    """Enemy records of every area (docs/re/notes.md, "Enemy records"): [{'image', 'start', 'end', 'ptrs', 'records'}].
    Image header: u16 end of the record section, u16 n, n u16 enemy blocks, 0, 4 more u16 section offsets, the last one
    = start of the records. Enemy block + 6 = u16 pointer to its record. Names and lines are plain SJIS, `$0`-`$3` = name
    placeholder, `$n` = newline (71:$752A)."""
    out = [enemy_area(iso[b:b + 0x10000], b) for b in range(ENEMY, min(len(iso), MIRROR), 0x40000)]
    return [a for a in out if a]


def enemy_area(img, base):
    end, n = img[0] | img[1] << 8, img[2] | img[3] << 8
    if not 1 <= n <= 12:
        return None
    w = [img[4 + 2 * i] | img[5 + 2 * i] << 8 for i in range(n + 5)]
    if w[n] != 0 or w[n + 1] != 4 + 2 * (n + 5) or not end <= 0x8000:   # w[-1] is also enemy 0's record pointer
        return None
    ptrs = [w[i] + 6 for i in range(n)]
    recs = {p: enemy_record(img, p) for p in sorted(set(img[x] | img[x + 1] << 8 for x in ptrs))}
    return {'image': base, 'start': w[-1], 'end': end, 'ptrs': ptrs, 'records': recs}


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
