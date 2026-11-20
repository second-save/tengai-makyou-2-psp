#!/usr/bin/env python3
"""Find the UI strings of the main program (menus, shops, battle commands) and write them as a reviewable list.

  mainstr.py ISO OUT.json [--start 0x41000] [--end 0x62800]     list candidates
  mainstr.py insert BUILT.iso script/main.json                  write the English in place (after insert.py)

A string = bytes between two NULs that tokenise cleanly as the mixed encoding (SJIS pairs, one-byte kana A1-DF,
table glyphs 21-7F) plus layout codes; codes 02 03 14 15 take one raw argument byte here (cursor x / y, colour).
Kept when it has at least two kana / kanji and every byte belongs to a token (a heuristic: code can pass it too, so
only strings given English in script/main.json are ever rewritten). Each entry: offset, hex, text (codec.decode).
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from codec import Codec

ARG1 = {0x02, 0x03, 0x14, 0x15}
ARG4 = {0x16, 0x18}   # windows: 4 raw bytes (x, y, w, h with bit 7 set)
CTRL = {0x01, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x12, 0x17, 0x1A, 0x1B}


def glyphs(b):
    """Number of kana / kanji in b, or -1 if a byte does not belong to a token."""
    i, n = 0, 0
    while i < len(b):
        c = b[i]
        if c in ARG1 or c in ARG4:
            i += 2 if c in ARG1 else 5
            continue
        if c in CTRL:
            i += 1
            continue
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEA:
            if i + 1 >= len(b) or not 0x40 <= b[i + 1] <= 0xFC or b[i + 1] == 0x7F:
                return -1
            try:
                b[i:i + 2].decode('shift_jis')
            except UnicodeDecodeError:
                return -1
            n, i = n + 1, i + 2
            continue
        if 0xA6 <= c <= 0xDF:
            n, i = n + 1, i + 1
            continue
        if 0x20 <= c <= 0x7E or c == 0xA0:
            i += 1
            continue
        return -1
    return n


def scan(iso, start, end):
    out, i = [], start
    while i < end:
        j = iso.index(b'\x00', i, end + 0x400) if b'\x00' in iso[i:end + 0x400] else end
        for k in range(max(0, j - i - 160), j - i):   # longest valid tail: a string can follow code, not a NUL
            b = iso[i + k:j]
            if glyphs(b) >= 2 and sum(1 for x in b if 0x20 <= x <= 0x7E) * 2 <= len(b) and (b[0] < 0x20 or b[0] >= 0x81):
                out.append((i + k, b))
                break
        i = j + 1
    return out


MIRROR = 0x8000000
EN = re.compile(r'\{([0-9A-F]{2})\}|\[([0-9A-F]{2})\]|(.)', re.S)


def render(b, c):
    """Lossless template: codes {XX}, their argument bytes [XX], glyphs as text (what main.json's `en` mirrors)."""
    out, i, mode = [], 0, 'h'
    while i < len(b):
        x = b[i]
        n = 2 if x in ARG1 else 5 if x in ARG4 else 1 if x < 0x20 else 0
        if n:
            out.append('{%02X}' % x + ''.join('[%02X]' % y for y in b[i + 1:i + n]))
            mode = {0x0E: 'k', 0x0F: 'h'}.get(x, mode)
            i += n
        elif 0x81 <= x <= 0x9F or 0xE0 <= x <= 0xEA:
            out.append(b[i:i + 2].decode('shift_jis', 'replace'))
            i += 2
        else:
            out.append(c.dec.get((mode, x), c.dec.get(('h', x), '[%02X]' % x)))
            i += 1
    return ''.join(out)


def encode(en):
    out = bytearray()
    for code, arg, ch in EN.findall(en):
        if code or arg:
            out.append(int(code or arg, 16))
        elif ' ' <= ch <= '~':
            out += ch.encode()
        else:
            raise ValueError('no glyph for %r in %r' % (ch, en))
    return bytes(out)


def insert(built, main_json):
    """Rewrite every entry with English in place (both copies of the track start), padded with NULs; log the writes."""
    iso = bytearray(open(built, 'rb').read())
    log, bad = [], 0
    for e in json.load(open(main_json, encoding='utf-8')):
        if not e.get('en'):
            continue
        at, old = int(e['at'], 16), bytes.fromhex(e['hex'])
        new = encode(e['en'])
        if iso[at:at + len(old)] != old or len(new) > len(old):
            print('%s: %s' % (e['at'], 'bytes differ' if iso[at:at + len(old)] != old else
                                 'English %d bytes, room %d' % (len(new), len(old))))
            bad += 1
            continue
        new = new.ljust(len(old), bytes.fromhex(e.get('pad', '00')))   # lists read by skipping NULs: pad '20'
        for o in (at, at + MIRROR):
            iso[o:o + len(old)] = new
            log.append('%x %s %s main %s' % (o, old.hex(), new.hex(), e['at']))
    open(built, 'wb').write(iso)
    open(built + '.writes', 'a').write('\n'.join(log) + '\n')
    print('%d main-program strings written, %d refused' % (len(log) // 2, bad))
    return bad


def main():
    a = sys.argv[1:]
    if a[0] == 'insert':
        sys.exit(1 if insert(a[1], a[2]) else 0)
    start = int(a[a.index('--start') + 1], 0) if '--start' in a else 0x41000
    end = int(a[a.index('--end') + 1], 0) if '--end' in a else 0x62800
    iso = open(a[0], 'rb').read()
    c = Codec()
    rows = [{'at': '%X' % o, 'hex': b.hex(), 'jp': render(b, c)} for o, b in scan(iso, start, end)]
    json.dump(rows, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(rows), 'strings')


if __name__ == '__main__':
    main()
