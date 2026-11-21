#!/usr/bin/env python3
"""Opening credit card "制作・総指揮 工藤裕司" (intro program 0x9F, shown at f~540-700) -> English.

  card.py render ISO SHOT.png OUT.png         indexed picture of the 256x256 screen (colours from a screenshot)
  card.py make ISO SYSCARD OUT                English card -> OUT.tiles, OUT.map (+ OUT.png preview)
  card.py insert BUILT.iso OUT                write both streams (both disc copies), log to BUILT.iso.writes

Tiles: resource `[flags 00][u16 count 0x40]` + plain LZ (ring A) of count 4bpp tiles, in intro bank 70 at $9B31
(streamed to VRAM tile 0x100 by 69:$43B9). Map: plain LZ in the intro's ADPCM image at ADPCM $1EE2 (ADPCM $0000 =
iso 0x27EF000), read by 69:$4522 through AD_READ: 32x32 u16 words, entry = 0x100 + running sum (palette 0).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz
from panel import tile_px, px_tile, draw, width

PROG = (0x9F * 128 + 2) * 0x800
TILES = PROG + (0x70 - 0x69) * 0x2000 + 0x9B31 - 0x8000
MAP, MAP_ROOM = 0x27EF000 + 0x1EE2, 0x1FCD - 0x1EE2    # up to a table read at ADPCM $1FCD (f=270)
MIRROR, W, H, BASE = 0x8000000, 32, 32, 0x100
# line, top y (the kanji line was y 114-129), x shift from centred; tile-aligned so the two lines take 4 tile rows,
# shifts picked as the smallest map stream (its room is tight)
TEXT = (('Executive Producer', 104, 2), ('Yuji Kudo', 120, 2))


def load(iso):
    assert iso[TILES:TILES + 3] == b'\x00\x40\x00', iso[TILES:TILES + 3].hex()
    tiles, tend = lz.unpack(iso, TILES + 3, size=0x40 * 32)
    raw, mend = lz.unpack(iso, MAP, size=W * H * 2)
    acc, m = 0, []
    for i in range(W * H):
        acc = (acc + (raw[2 * i] | raw[2 * i + 1] << 8)) & 0xFFFF
        m.append(acc + BASE)
    return tiles, tend - TILES - 3, m, mend - MAP


def render(iso_path, shot, out):
    from PIL import Image
    tiles, _, m, _ = load(open(iso_path, 'rb').read())
    ref = Image.open(shot).convert('RGB')
    img, pal = Image.new('P', (W * 8, H * 8)), {}
    for ty in range(H):
        for tx in range(W):
            for y, row in enumerate(tile_px(tiles, m[ty * W + tx] & 0x7FF)):
                for x, c in enumerate(row):
                    img.putpixel((tx * 8 + x, ty * 8 + y), c)
                    if ty * 8 + y < ref.height:
                        pal.setdefault(c, ref.getpixel((tx * 8 + x, ty * 8 + y)))
    flat = []
    for i in range(256):
        flat += pal.get(i, (255, 0, 255))
    img.putpalette(flat)
    img.save(out)
    print('colours used:', sorted(pal))


def make(iso_path, syscard, out):
    from PIL import Image
    iso, card = open(iso_path, 'rb').read(), open(syscard, 'rb').read()
    tiles0, tsize, _, msize = load(iso)
    img = Image.new('P', (W * 8, H * 8), 2)   # 2 = navy background, 14 = white, 1 = black shadow (as the kanji)
    for s, y, dx in TEXT:   # System Card 8x8 glyphs at 2x (2-px strokes like the bold kanji), proportional, centred
        draw(img, card, (W * 8 - width(card, s, 2)) // 2 + dx, y, s, 14, 2, edge=1)
    tiles, index, m = [], {}, []
    for ty in range(H):
        for tx in range(W):
            t = px_tile([[img.getpixel((tx * 8 + x, ty * 8 + y)) for x in range(8)] for y in range(8)])
            if t not in index:
                index[t] = len(tiles); tiles.append(t)
            m.append(BASE + index[t])
    # more than the original 0x40 tiles: the count grows (VRAM tiles 0x140+ hold nothing during the card; checked
    # by comparing the intro frames that follow with the original build)
    assert len(tiles) <= 0x50, '%d tiles' % len(tiles)
    data = b''.join(tiles)
    tblock = bytes([0, len(tiles), 0]) + lz.pack_best(data)   # header: flags, u16 tile count
    words, prev = bytearray(), 0
    for e in m:
        d = (e - BASE - prev) & 0xFFFF
        words += bytes([d & 255, d >> 8]); prev = e - BASE
    mblock = lz.pack_best(bytes(words))
    print('%d tiles, tile stream %d of %d bytes, map stream %d of %d bytes' % (len(tiles), len(tblock), tsize,
                                                                                len(mblock), MAP_ROOM))
    assert len(tblock) <= tsize + 3 and len(mblock) <= MAP_ROOM, 'does not fit'
    assert lz.unpack(tblock, 3, size=len(data))[0] == data and lz.unpack(mblock, 0, size=len(words))[0] == words
    img.putpalette([0, 0, 0, 0, 0, 0, 1, 0, 75] + [0, 0, 0] * 11 + [255, 255, 255] + [0, 0, 0] * 241)
    img.save(out + '.png')
    open(out + '.tiles', 'wb').write(tblock)
    open(out + '.map', 'wb').write(mblock)


def insert(built, out):
    iso = bytearray(open(built, 'rb').read())
    log = []
    for at, path in ((TILES, out + '.tiles'), (MAP, out + '.map')):
        data = open(path, 'rb').read()
        old = iso[at:at + len(data)]
        for o in (at, at + MIRROR):
            assert iso[o:o + len(data)] == old, 'mirror differs at %x' % o
            log.append('%x %s %s opening card' % (o, old.hex(), data.hex()))
            iso[o:o + len(data)] = data
    open(built, 'wb').write(iso)
    open(built + '.writes', 'a').write('\n'.join(log) + '\n')
    print('opening card written')


if __name__ == '__main__':
    {'render': render, 'make': make, 'insert': insert}[sys.argv[1]](*sys.argv[2:5])
