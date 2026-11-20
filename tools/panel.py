#!/usr/bin/env python3
"""Start menu panel (the 起 / 転 screen before the title): bank 78 resource 0 at iso 0x5F000.

  panel.py render ISO SHOT.png OUT.png       indexed picture of the 32x32-tile screen (colours taken from a screenshot)
  panel.py build ISO IN.png OUT.bin          tiles + map from an edited picture -> new resource bytes (same size or less)
  panel.py make ISO SYSCARD OUT.bin [SHOT.png]  English panel (TEXT, BUTTONS below) -> OUT.bin + OUT.bin.png preview
  panel.py insert BUILT.iso RES.bin          write it at 0x5F000 and the mirror, log to BUILT.iso.writes

Resource: u16 size (0xD3E), u16 8, u16 tile block, u16 map block, 37 bytes (palette?). Tile block: u16 word count
(bit 15 = high bytes from ring B) + lz.pack_rings stream, loaded at tile 256. Map block: w, h + lz stream of w*h
u16 deltas; entry = running sum + 0xE100 (palette 14, tile 256). Traced 2026-11-21: tiles 69:$4681, map 70:$6AE8.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz

AT, BASE, MIRROR = 0x5F000, 0xE100, 0x8000000


def load(iso):
    size, _, ta, ma = struct.unpack_from('<4H', iso, AT)
    hdr = iso[AT + ta:AT + ta + 2]
    tiles, _ = lz.unpack_rings(iso, AT + ta + 2, lz.gfx_rings(hdr))
    w, h = iso[AT + ma], iso[AT + ma + 1]
    raw, _ = lz.unpack(iso, AT + ma + 2, size=w * h * 2)
    acc, m = 0, []
    for i in range(w * h):
        acc = (acc + (raw[2 * i] | raw[2 * i + 1] << 8)) & 0xFFFF
        m.append((acc + BASE) & 0xFFFF)
    return size, ta, ma, hdr, tiles, w, h, m


def tile_px(tiles, t):
    d = tiles[(t - 256) * 32:(t - 256) * 32 + 32]
    return [[(d[2 * y] >> 7 - x & 1) | (d[2 * y + 1] >> 7 - x & 1) << 1 | (d[16 + 2 * y] >> 7 - x & 1) << 2 |
             (d[17 + 2 * y] >> 7 - x & 1) << 3 for x in range(8)] for y in range(8)]


def px_tile(p):
    d = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = p[y][x]
            for k, off in enumerate((2 * y, 2 * y + 1, 16 + 2 * y, 17 + 2 * y)):
                d[off] |= (c >> k & 1) << 7 - x
    return bytes(d)


def render(iso_path, shot, out):
    from PIL import Image
    _, _, _, _, tiles, w, h, m = load(open(iso_path, 'rb').read())
    img = Image.new('P', (w * 8, h * 8))
    ref = Image.open(shot).convert('RGB') if shot else Image.new('RGB', (1, 1))
    pal = {}
    for ty in range(h):
        for tx in range(w):
            e = m[ty * w + tx]
            for y, row in enumerate(tile_px(tiles, e & 0x7FF)):
                for x, c in enumerate(row):
                    i = (e >> 12) * 16 + c
                    img.putpixel((tx * 8 + x, ty * 8 + y), i)
                    if ty * 8 + y < ref.height and tx * 8 + x < ref.width:
                        pal.setdefault(i, ref.getpixel((tx * 8 + x, ty * 8 + y)))
    flat = []
    for i in range(256):
        flat += pal.get(i, (255, 0, 255))
    img.putpalette(flat)
    img.save(out)
    print('palette entries seen:', sorted(pal))


def build(iso_path, png, out):
    """Re-tile an edited indexed picture: every 8x8 cell keeps one palette (its pixels' index // 16)."""
    from PIL import Image
    iso = open(iso_path, 'rb').read()
    size, ta, ma, hdr, _, w, h, _ = load(iso)
    img = Image.open(png)
    assert img.mode == 'P' and img.size == (w * 8, h * 8), (img.mode, img.size)
    tiles, index, m = [], {}, []
    for ty in range(h):
        for tx in range(w):
            px = [[img.getpixel((tx * 8 + x, ty * 8 + y)) for x in range(8)] for y in range(8)]
            pals = {c // 16 for r in px for c in r}
            assert len(pals) == 1, 'cell %d,%d mixes palettes %s' % (tx, ty, pals)
            t = px_tile([[c & 15 for c in r] for r in px])
            if t not in index:
                index[t] = len(tiles); tiles.append(t)
            m.append(pals.pop() << 12 | 256 + index[t])
    data = b''.join(tiles)
    n = len(data) // 2
    th = bytes([n & 255, n >> 8 | hdr[1] & 0x80])
    tblock = th + lz.pack_rings(data, lz.gfx_rings(th))
    deltas, prev = bytearray(), 0
    for e in m:
        d = (e - BASE - prev) & 0xFFFF
        deltas += bytes([d & 255, d >> 8]); prev = (e - BASE) & 0xFFFF
    mblock = bytes([w, h]) + lz.pack_best(bytes(deltas))
    res = bytearray(iso[AT:AT + ta]) + tblock
    struct.pack_into('<H', res, 6, len(res))
    res += mblock
    print('%d tiles (was %d), tile block %d, map block %d, resource %d of %d bytes' %
          (len(tiles), (hdr[0] | (hdr[1] & 0x7F) << 8) >> 4, len(tblock), len(mblock), len(res), size))
    assert len(res) <= size, 'does not fit'
    res += iso[AT + len(res):AT + size]   # keep the old tail bytes (unread)
    struct.pack_into('<H', res, 0, size)
    # self-check: decode what we wrote
    chk = bytearray(iso); chk[AT:AT + size] = res
    assert load(bytes(chk))[7] == m and load(bytes(chk))[4] == data
    open(out, 'wb').write(res)


TEXT = [('To start from the', 0), ('very beginning,', 0), ('choose ', 0, 'NEW', 1, '.', 0), ('To pick up where', 0),
        ('you left off,', 0), ('choose ', 0, 'LOAD', 1, '.', 0), ('Make your pick!!', 0)]
BUTTONS = ((40, 104, 'NEW'), (152, 216, 'LOAD'))   # button interiors x0..x1 (rows y 160..216): 起 / 転 replaced


def font(card, c):
    """System Card 8x8 glyph rows of c and its ink columns (the dialogue VWF uses the same glyphs)."""
    rows = card[0x2000 + ord(c) * 8:][:8]
    ink = 0
    for r in rows:
        ink |= r
    return rows, ink


def draw(img, card, x, y, s, colour, scale=1, edge=None):
    for c in s:
        rows, ink = font(card, c)
        if not ink:
            x += 4 * scale
            continue
        left, right = 8 - ink.bit_length(), (ink & -ink).bit_length() - 1
        for gy, r in enumerate(rows):
            for gx in range(left, 8 - right):
                if r >> 7 - gx & 1:
                    for dy in range(scale):
                        for dx in range(scale):
                            px, py = x + (gx - left) * scale + dx, y + gy * scale + dy
                            if edge is not None and img.getpixel((px + 1, py + 1)) != colour:
                                img.putpixel((px + 1, py + 1), edge)
                            img.putpixel((px, py), colour)
        x += (8 - left - right + 1) * scale
    return x


def width(card, s, scale=1):
    w = 0
    for c in s:
        rows, ink = font(card, c)
        w += 4 * scale if not ink else (ink.bit_length() - (ink & -ink).bit_length() + 2) * scale
    return w - scale


SPR = AT + 0xD3E   # resource 1: u16 size 0x40F, u16 8 (sprite block: 32 cells of 16x16, the highlighted buttons), ...


def sprite_cells(iso):
    hdr = iso[SPR + 8:SPR + 10]
    data, end = lz.unpack_rings(iso, SPR + 10, lz.gfx_rings(hdr))
    return hdr, data, end - SPR


def cell_px(d):
    w = [d[2 * i] | d[2 * i + 1] << 8 for i in range(64)]
    return [[sum((w[p * 16 + y] >> 15 - x & 1) << p for p in range(4)) for x in range(16)] for y in range(16)]


def px_cell(p):
    w = [0] * 64
    for y in range(16):
        for x in range(16):
            for k in range(4):
                w[k * 16 + y] |= (p[y][x] >> k & 1) << 15 - x
    return b''.join(bytes([v & 255, v >> 8]) for v in w)


def highlight(iso, card):
    """Selected-button sprites (two 32x64 sprites per button, SAT: pattern 0x120 at x 40 and 0x140 at x 72; the
    right button uses cells +8): kanji pixels (2, edge 3) cleared to 1, the button's word drawn as on the BG."""
    hdr, data, end = sprite_cells(iso)
    cells = [cell_px(data[i * 128:i * 128 + 128]) for i in range(32)]
    for b, (x0, x1, word) in enumerate(BUTTONS):
        pic = [[0] * 64 for _ in range(64)]
        for half, base in ((0, 0), (1, 16)):
            for k in range(8):
                c = cells[base + b * 8 + k]
                for y in range(16):
                    for x in range(16):
                        pic[k // 2 * 16 + y][half * 32 + k % 2 * 16 + x] = c[y][x]

        class Pic:   # the few calls draw() makes, on the 64x64 list
            def getpixel(self, p): return pic[p[1]][p[0]]
            def putpixel(self, p, v): pic[p[1]][p[0]] = v
        for y in range(56):
            for x in range(64):
                if pic[y][x] in (2, 3):
                    pic[y][x] = 1
        w = width(card, word, 2)
        draw(Pic(), card, (x1 - x0 - w) // 2, 20, word, 2, 2, edge=3)
        for half, base in ((0, 0), (1, 16)):
            for k in range(8):
                cells[base + b * 8 + k] = [row[half * 32 + k % 2 * 16:half * 32 + k % 2 * 16 + 16]
                                           for row in pic[k // 2 * 16:k // 2 * 16 + 16]]
    new = b''.join(px_cell(c) for c in cells)
    block = hdr + lz.pack_rings(new, lz.gfx_rings(hdr))
    room = struct.unpack_from('<H', iso, SPR + 4)[0] - 8   # up to the next block of the resource
    print('highlight sprites: block %d of %d bytes' % (len(block), room))
    assert len(block) <= room, 'highlight sprites do not fit'
    assert lz.unpack_rings(block, 2, lz.gfx_rings(hdr))[0] == new
    return SPR + 8, block


def insert(built, res_path):
    """Write the resource over the original one (both copies of the track start) and log the writes."""
    iso, res = bytearray(open(built, 'rb').read()), open(res_path, 'rb').read()
    log = []
    for o in (AT, AT + MIRROR):
        assert len(iso) > o + len(res)
        log.append('%x %s %s panel' % (o, iso[o:o + len(res)].hex(), res.hex()))
        iso[o:o + len(res)] = res
    open(built, 'wb').write(iso)
    open(built + '.writes', 'a').write('\n'.join(log) + '\n')
    print('start panel written (%d bytes)' % len(res))


def make(iso_path, syscard, out, shot=None):
    """Original panel -> English panel picture (OUT.png, colours from SHOT if given) and resource (OUT)."""
    from PIL import Image
    card = open(syscard, 'rb').read()
    render(iso_path, shot, out + '.orig.png')
    img = Image.open(out + '.orig.png')
    for y in range(24, 136):                 # text box interior (tiles 3-18 x 3-16)
        for x in range(24, 152):
            img.putpixel((x, y), 239)
    for i, line in enumerate(TEXT):
        x = 28
        for k in range(0, len(line), 2):
            x = draw(img, card, x, 28 + 16 * i, line[k], (225, 227)[line[k + 1]])
        assert x <= 150, line
    for x0, x1, word in BUTTONS:
        for y in range(160, 216):
            for x in range(x0, x1):
                if img.getpixel((x, y)) in (243, 244):
                    img.putpixel((x, y), 241)
        w = width(card, word, 2)
        assert w <= x1 - x0 - 4, word
        draw(img, card, x0 + (x1 - x0 - w) // 2, 180, word, 243, 2, edge=244)
    img.save(out + '.png')
    build(iso_path, out + '.png', out)
    iso = open(iso_path, 'rb').read()
    at, block = highlight(iso, card)
    res = open(out, 'rb').read()
    assert AT + len(res) == SPR
    open(out, 'wb').write(res + iso[SPR:at] + block)   # one span: panel resource, resource 1 header, sprite block


if __name__ == '__main__':
    {'render': render, 'build': build, 'make': make, 'insert': insert}[sys.argv[1]](*sys.argv[2:6])
