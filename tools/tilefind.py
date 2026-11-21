#!/usr/bin/env python3
"""Find which 8x8 VRAM tiles draw a screen region: matches the colour-equality pattern of each 8x8 cell of a screenshot
against every 4bpp tile of a VRAM dump (palette-independent), at the scroll offset that matches best.

  tilefind.py SHOT.png VRAM.bin x,y,w,h      -> prints per cell: screen x,y and matching tile numbers

Needs Pillow. shortcut: exact pattern match only (a tile flipped or sharing two palettes is missed), fine for map signs.
"""
import sys
from PIL import Image


def tile(v, n):
    t = v[n * 32:n * 32 + 32]
    return tuple(((t[2 * r] >> (7 - c)) & 1) | ((t[2 * r + 1] >> (7 - c)) & 1) << 1 | ((t[16 + 2 * r] >> (7 - c)) & 1) << 2
                 | ((t[17 + 2 * r] >> (7 - c)) & 1) << 3 for r in range(8) for c in range(8))


def canon(px):
    m, out = {}, []
    for p in px:
        out.append(m.setdefault(p, len(m)))
    return tuple(out)


def main():
    img = Image.open(sys.argv[1]).convert('RGB')
    sx = img.width / 256  # screenshots may be scaled
    v = open(sys.argv[2], 'rb').read()
    x0, y0, w, h = map(int, sys.argv[3].split(','))
    lib = {}
    for n in range(len(v) // 32):
        lib.setdefault(canon(tile(v, n)), []).append(n)
    best = None
    for dy in range(8):
        for dx in range(8):
            hits = []
            for y in range(y0 + dy, y0 + h - 7, 8):
                for x in range(x0 + dx, x0 + w - 7, 8):
                    c = canon([img.getpixel((int((x + i) * sx), int((y + j) * sx))) for j in range(8) for i in range(8)])
                    if len(set(c)) > 1 and c in lib:
                        hits.append((x, y, lib[c][:6]))
            if not best or len(hits) > len(best[1]):
                best = ((dx, dy), hits)
    print('offset', best[0], 'cells matched', len(best[1]))
    for x, y, ns in best[1]:
        print(x, y, ' '.join('%03X' % n for n in ns))


if __name__ == '__main__':
    main()
