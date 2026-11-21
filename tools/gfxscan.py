#!/usr/bin/env python3
"""Static sweep of graphics blocks in every area's event block (sectors area*128+2, 128 sectors), for the graphics-text survey.

  gfxscan.py ISO OUT_DIR [AREA...] [--pal X.pal.bin]   (hex areas; default 0x00-0xFF with an event block)

Finds resources of the form [u16 x][u16 off0 = 8 + 2*extra][u16 off...][0] at S, where S+off is a graphics LZ block
(69:$4681 header: u16 word count, bit 15 = high bytes from ring B; decoded with lz.unpack_rings). Map tilesets use it
(6A:$6201 walks the list; e.g. area 0x10 village at block 0x18D0E: 0x18D16 -> VRAM $1000, 0x19EDA -> $1C00), so do
panel-style resources (u16 size, u16 8, tile block, map block). Writes OUT/<area>_<offset>.png (16 tiles a row, so a
16x16 metatile stored TL TR (row) / BL BR (row + 16) reads whole), skipping exact duplicates across areas, and
OUT/index.tsv (area, block offset, words, file, first area seen). Prints every candidate it rejected and why.
"""
import hashlib, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lz
import extract

TILES = os.path.join(os.environ.get('TRANSLATE_SKILL', os.path.expanduser('~/.claude/skills/translate-retro-game')),
                     'scripts/tiles.py')


def block(blk, p):
    """Decode the graphics block at p, or None when it is not one (bad count, runs off the slot, not whole tiles)."""
    if p + 2 > len(blk):
        return None
    n = blk[p] | (blk[p + 1] & 0x7F) << 8
    if n < 16 or n % 16 or n > 0x4000:
        return None
    try:
        data, end = lz.unpack_rings(blk, p + 2, lz.gfx_rings(blk[p:p + 2]))
    except IndexError:
        return None
    return data, end


def resources(blk):
    """Yield (S, [block offsets]) for tileset descriptors: u16 0, then 1-2 signed u16 offsets from S (16-bit wrap: a sub
    shares another sub's block by pointing back to it, e.g. area 0x10 shop at 0x1CE77 -> -0x4161 = village 0x18D16), then 0;
    one entry is 8 (the descriptor's own block, right after it) and that block decodes."""
    def u16(o):
        return blk[o] | blk[o + 1] << 8
    for s in range(0, len(blk) - 10):
        if u16(s) or 8 not in (u16(s + 2), u16(s + 4)):
            continue
        es = [u16(s + 2)] if not u16(s + 4) else [u16(s + 2), u16(s + 4)] if not u16(s + 6) else None
        if not es or 0 in es:
            continue
        offs = [s + (e - 0x10000 if e & 0x8000 else e) for e in es]
        if all(0 <= o < len(blk) for o in offs) and block(blk, s + 8):
            yield s, offs


def adpcm_tilesets(img):
    """Tilesets streamed from the area's ADPCM image (sectors area*128+98, 64K; 6A:$61B8 -> 69:$498C A=2): t = u16 at
    u16 at 0; table of block addresses from t+2 up to the first block (area 0x10: 0x3A76 overworld, 0x6B92)."""
    def u16(o):
        return img[o] | img[o + 1] << 8
    t = u16(u16(0))
    offs, o = [], t + 2
    while t + 2 <= o < len(img) - 2 and (not offs or o < min(offs)) and len(offs) < 6:
        e = u16(o)
        if not t < e < len(img):
            break
        offs.append(e); o += 2
    return offs


def main():
    args = sys.argv[1:]
    pal = []
    if '--pal' in args:   # a BGR555 palette for tiles.py, e.g. high contrast to read sign kanji
        i = args.index('--pal'); pal = ['--pal', args[i + 1]]; del args[i:i + 2]
    iso = open(args[0], 'rb').read()
    out = args[1]
    os.makedirs(out, exist_ok=True)
    areas = [int(a, 16) for a in args[2:]] or range(0x100)
    seen, rows = {}, []

    def emit(a, src, buf, p, why):
        r = block(buf, p)
        if not r:
            print('area %02X %s: %05X is not a graphics block (%s)' % (a, src, p, why))
            return
        data = r[0]
        h = hashlib.sha1(data).hexdigest()
        if h in seen:
            rows.append('%02X\t%s\t%05X\t%d\t%s\tdup' % (a, src, p, len(data) // 2, seen[h]))
            return
        name = '%02X_%s_%05X' % (a, src, p)
        seen[h] = name
        binp = os.path.join(out, name + '.bin')
        open(binp, 'wb').write(data)
        subprocess.run([sys.executable, TILES, 'render', '--fmt', 'snes4', '--zoom', '2', '--cols', '16'] + pal + [binp,
                        os.path.join(out, name + '.png')], stdout=subprocess.DEVNULL, check=True)
        os.remove(binp)
        rows.append('%02X\t%s\t%05X\t%d\t%s\t' % (a, src, p, len(data) // 2, name))

    for a in areas:
        base = (a * 128 + 2) * 2048
        blk = iso[base:base + 128 * 2048]
        if not re.match(extract.SIG, blk, re.S):
            continue
        done = set()
        for s, offs in resources(blk):
            for p in offs:
                if p not in done:
                    done.add(p)
                    emit(a, 'ev', blk, p, 'entry of descriptor %05X: map or other data' % s)
        img = iso[(a * 128 + 98) * 2048:][:0x10000]
        for p in adpcm_tilesets(img):
            emit(a, 'ad', img, p, 'ADPCM tileset table entry')
    open(os.path.join(out, 'index.tsv'), 'w').write('area\tsrc\tblock\twords\tfile\tnote\n' + '\n'.join(rows) + '\n')
    print(len(seen), 'distinct blocks,', len(rows), 'block entries')


if __name__ == '__main__':
    main()
