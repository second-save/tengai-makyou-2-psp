#!/usr/bin/env python3
"""Message bytes <-> readable text, byte-exact both ways.

  codec.py test BLOCKS.json     roundtrip every extracted message and dictionary word

Text form: glyphs from tools/table.json (learned by align.py), newline = 0D, `{k}`/`{h}` = katakana/hiragana switch
(0E/0F), `{w:NN}` = dictionary word (1F nn, kept unexpanded), `{XX}` = any other control code, `[XX]` = a byte with no
glyph (also used for an SJIS pair whose character has a one-byte code, so encoding picks the same bytes back).
Arguments of control codes are ordinary bytes here: decimal arguments show as full-width digits.
"""
import json, os, re, sys

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'table.json')
TOKEN = re.compile(r'\{w:([0-9A-F]{2})\}|\{([0-9A-F]{2})\}|\[([0-9A-F]{2})\]|\{([hk])\}|(.)', re.S)


class Codec:
    def __init__(self, path=TABLE):
        t = json.load(open(path, encoding='utf-8'))
        self.dec = {(k[0], int(k[1:], 16)): v for k, v in t.items() if len(k) == 3}
        self.enc = {}
        for (mode, b), ch in sorted(self.dec.items()):
            self.enc.setdefault((mode, ch), b)
        self.single = set(self.dec.values())

    def decode(self, m, strict=True):
        """strict=False reads better (every SJIS pair shows as its character) but does not encode back to the same bytes."""
        out, i, mode = [], 0, 'h'
        while i < len(m):
            c = m[i]
            i += 1
            if c == 0x0D:
                out.append('\n')
            elif c == 0x0E or c == 0x0F:
                mode = 'k' if c == 0x0E else 'h'
                out.append('{%s}' % mode)
            elif c == 0x1F and i < len(m):
                out.append('{w:%02X}' % m[i])
                i += 1
            elif c < 0x20:
                out.append('{%02X}' % c)
            elif (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEA) and i < len(m):
                try:
                    ch = m[i - 1:i + 1].decode('cp932')
                    ok = len(ch) == 1 and (not strict or ch not in self.single) and ch not in '{}[]\n' and ch.encode('cp932') == m[i - 1:i + 1]
                except UnicodeError:
                    ok = False
                if ok:
                    out.append(ch)
                    i += 1
                else:
                    out.append('[%02X]' % c)  # the trail byte follows as its own token
            else:
                key = (mode if 0x61 <= c <= 0x79 or c >= 0xA1 else 'h', c)
                ch = self.dec.get(key)
                out.append(ch if ch and self.enc[(key[0], ch)] == c else '[%02X]' % c)
        return ''.join(out)

    def encode(self, s):
        out, mode = bytearray(), 'h'
        for w, ctl, raw, sw, ch in TOKEN.findall(s):
            if w:
                out += bytes([0x1F, int(w, 16)])
            elif ctl:
                out.append(int(ctl, 16))
            elif raw:
                out.append(int(raw, 16))
            elif sw:
                mode = sw
                out.append(0x0E if sw == 'k' else 0x0F)
            elif ch == '\n':
                out.append(0x0D)
            elif (mode, ch) in self.enc or ('h', ch) in self.enc and not 0x61 <= self.enc[('h', ch)] <= 0x79 and self.enc[('h', ch)] < 0xA1:
                out.append(self.enc.get((mode, ch), self.enc.get(('h', ch))))
            else:
                out += ch.encode('cp932')
        return bytes(out)


def test(blocks_path):
    c = Codec()
    seen, bad, raw = set(), 0, 0
    for b in json.load(open(blocks_path)):
        for g in b['groups']:
            for h in g['msgs']:
                if h in seen:
                    continue
                seen.add(h)
                m = bytes.fromhex(h)
                t = c.decode(m)
                raw += '[' in t
                if c.encode(t) != m:
                    bad += 1
                    if bad <= 5:
                        print('MISMATCH', h, repr(t), c.encode(t).hex())
    print(len(seen), 'distinct messages,', bad, 'roundtrip failures,', raw, 'with raw [XX] bytes')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(test(sys.argv[2]) if sys.argv[1:2] == ['test'] else print(__doc__))
