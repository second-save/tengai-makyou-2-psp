#!/usr/bin/env python3
"""Ending staff roll (program 0x9E, bank 0x78 of it; see docs/re/notes.md "Ending staff roll").

  roll.py extract ISO script/roll.json      records -> JSON (keeps an existing file's "en")
  roll.py insert BUILT.iso script/roll.json rewrite the roll in place (both disc copies)

Bank layout: u16 pointer table (entry 0 = 0x0002 = the roll), then records: colour byte (1 = heading), 2-byte cells
(SJIS, `01 nn` = the game's own glyph, two ASCII bytes = two 8x8 glyphs, src/roll.s), `00 00`. A record starting
with `00 00` ends the roll. At most 16 cells (32 ASCII characters) per line.
"en": "" = keep the original bytes; "left|right" = left part from column 2 (1 if tight), right part ending at column 32 (as the
Japanese names end in the last cell); text with no "|" is centred. Text with `{01xx}` (a raw cell: the clear-time
digits) is written as is, so its ASCII runs must have even lengths.
"""
import json, re, sys

BANK = (0x9E * 128 + 2) * 0x800 + (0x78 - 0x69) * 0x2000
MIRROR = 0x8000000
COLS = 32


def records(iso):
    b = iso[BANK:BANK + 0x2000]
    assert b[:2] == b'\x02\x00', b[:2].hex()
    i, out = 2, []
    while b[i:i + 2] != b'\x00\x00':
        j, cells = i + 1, []
        while b[j:j + 2] != b'\x00\x00':
            cells.append(b[j:j + 2]); j += 2
        out.append((b[i], cells))
        i = j + 2
    return out, i + 2, b


def jp(cells):
    return ''.join('{%s}' % x.hex() if x[0] < 0x80 else x.decode('cp932') for x in cells)


def layout(c, en):
    if '|' in en:
        left, right = en.split('|')
        lead = min(2, COLS - 1 - len(left) - len(right))   # 1 column for the tightest lines
        assert lead >= 1, 'line %r too long' % en
        s = (' ' * lead + left).ljust(COLS - len(right)) + right
    else:
        s = en.center(COLS)
    s = s.rstrip()
    if len(s) % 2:
        s += ' '
    return s


def encode(c, en, cells):
    if not en:
        return bytes([c]) + b''.join(cells)
    raw = []
    for part in re.split(r'(\{[0-9a-f]{4}\})', en):
        raw.append(bytes.fromhex(part[1:-1]) if part.startswith('{') else part.encode('ascii'))
    if any(p.startswith('{') for p in re.findall(r'\{[0-9a-f]{4}\}', en)):
        s = b''.join(raw)          # raw cells: the line is given as is, cells aligned by hand
    else:
        s = layout(c, en).encode('ascii')
    assert len(s) % 2 == 0 and len(s) <= COLS, 'line %r: %d bytes' % (en, len(s))
    return bytes([c]) + s


def main():
    cmd, iso_path, js = sys.argv[1:4]
    iso = open(iso_path, 'rb').read()
    recs, end, b = records(iso)
    if cmd == 'extract':
        try:
            old = {r['n']: r['en'] for r in json.load(open(js))}
        except FileNotFoundError:
            old = {}
        out = [{'n': n, 'c': c, 'jp': jp(cells), 'en': old.get(n, '')} for n, (c, cells) in enumerate(recs)]
        json.dump(out, open(js, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('%d records, roll ends at bank offset 0x%X' % (len(out), end))
        return
    script = json.load(open(js, encoding='utf-8'))
    assert len(script) == len(recs)
    body = b''.join(encode(r['c'], r['en'], cells) + b'\x00\x00' for r, (c, cells) in zip(script, recs)) + b'\x00\x00'
    room = len(b.rstrip(b'\xff')) - 2
    assert len(body) <= 0x2000 - 2, 'roll needs 0x%X bytes' % len(body)
    new, log, n = bytearray(iso), [], max(len(body), room)
    for base in (BANK, BANK + MIRROR):
        assert iso[base:base + 0x2000] == b
        new[base + 2:base + 2 + n] = body.ljust(n, b'\xff')
        log.append('%x %s %s staff roll' % (base + 2, iso[base + 2:base + 2 + n].hex(), new[base + 2:base + 2 + n].hex()))
    open(iso_path, 'wb').write(new)
    open(iso_path + '.writes', 'a').write('\n'.join(log) + '\n')
    print('staff roll: %d records, 0x%X bytes (was 0x%X, room 0x%X)' % (len(script), len(body), end - 2, 0x1FFE))


if __name__ == '__main__':
    main()
