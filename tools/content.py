#!/usr/bin/env python3
"""CONTENT.DAT of Sony's PSP PC Engine emulator: unpack / pack.

Layout (after XOR with key[i&15] ^ table[i&511]): 0x80 header (file count at
0x28), 0x50-byte entries (name[0x40], u32 offset, u32 size, 8 zero), files
padded to 32. Data tracks (*.bin) are zlib chunks of 0x40000 bytes behind a
(count, [offset, size]*) table.

  content.py unpack CONTENT.DAT PSP-KEY.EDAT OUTDIR
  content.py pack   OUTDIR PSP-KEY.EDAT CONTENT.DAT [TRACK.iso]   (TRACK.iso replaces data track HCD1022_02.bin)
  content.py test   CONTENT.DAT PSP-KEY.EDAT     (identity self-check)

Needs tools/public.key (the 512-byte table above, not in this repo): take it from the community PCE_py_tool.
"""
import os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK = 0x40000


def xor(data, key):
    table = open(os.path.join(HERE, 'public.key'), 'rb').read()
    assert len(key) == 16 and len(table) == 512
    ks = bytes(key[i & 15] ^ table[i] for i in range(512))
    ks = (ks * (len(data) // 512 + 1))[:len(data)]
    n = int.from_bytes(data, 'little') ^ int.from_bytes(ks, 'little')
    return n.to_bytes(len(data), 'little')


def parse(plain):
    count = struct.unpack_from('<I', plain, 0x28)[0]
    files = []
    for i in range(count):
        e = plain[0x80 + i * 0x50:0xD0 + i * 0x50]
        name = e[:0x40].split(b'\0')[0].decode('ascii')
        off, size = struct.unpack_from('<II', e, 0x40)
        files.append((name, plain[off:off + size]))
    # the original pads files to 32 with leftover bytes, not zeros: keep them for identity
    pads = b''.join(plain[o + s:o + ((s + 31) & -32)] for o, s in
                    (struct.unpack_from('<II', plain, 0xC0 + i * 0x50) for i in range(count)))
    return plain[:0x80] + pads, files


def build(header, files):
    header, pads = header[:0x80], header[0x80:]
    out = bytearray(header)
    struct.pack_into('<I', out, 0x28, len(files))
    start = 0x80 + len(files) * 0x50
    for name, data in files:
        out += name.encode('ascii').ljust(0x40, b'\0') + struct.pack('<IIII', start, len(data), 0, 0)
        start += (len(data) + 31) & -32
    for name, data in files:
        n = -len(data) & 31
        out += data + pads[:n].ljust(n, b'\0')
        pads = pads[n:]
    return bytes(out)


def track_unpack(data):
    n = struct.unpack_from('<I', data, 0)[0]
    out = bytearray()
    for i in range(n):
        off, size = struct.unpack_from('<II', data, 4 + i * 8)
        out += zlib.decompressobj().decompress(data[off:off + size])
    return bytes(out)


def track_pack(raw, orig=None, orig_raw=None):
    """Compress a data track. With orig, keep its layout: unchanged chunks stay as they are and a changed chunk is
    written at its old offset when it fits (the rest of its old slot is left as it was), so the rest of CONTENT.DAT,
    whose XOR key depends on the file position, stays byte-identical and the release patch stays small. A chunk that
    does not fit goes at the end of the track (reported)."""
    n = (len(raw) + CHUNK - 1) // CHUNK
    if orig is None or struct.unpack_from('<I', orig, 0)[0] != n:
        out = bytearray(4 + n * 8)
        struct.pack_into('<I', out, 0, n)
        for i in range(n):
            comp = zlib.compress(raw[i * CHUNK:(i + 1) * CHUNK], 9)
            comp += bytes(-len(comp) & 3)
            struct.pack_into('<II', out, 4 + i * 8, len(out), len(comp))
            out += comp
        return bytes(out)
    out, late, holes = bytearray(orig), [], []
    for i in range(n):
        chunk = raw[i * CHUNK:(i + 1) * CHUNK]
        if orig_raw[i * CHUNK:(i + 1) * CHUNK] == chunk:
            continue
        off, size = struct.unpack_from('<II', orig, 4 + i * 8)
        comp = zlib.compress(chunk, 9)
        comp += bytes(-len(comp) & 3)
        holes.append([off, size])          # the old slot is free for whoever fits (itself first)
        late.append((i, comp))
    late.sort(key=lambda x: -len(x[1]))    # largest first, each into the smallest hole that holds it
    spare = [i for i in range(n) if orig_raw[i * CHUNK:(i + 1) * CHUNK] == raw[i * CHUNK:(i + 1) * CHUNK]]
    moved = 0
    for i, comp in late:
        while True:
            fit = [h for h in holes if h[1] >= len(comp)]
            if fit or not spare:
                break
            # make room: recompress an unchanged chunk at level 9 (smaller than Sony's), its saved tail becomes a hole
            j = spare.pop(0)
            off, size = struct.unpack_from('<II', orig, 4 + j * 8)
            c = zlib.compress(raw[j * CHUNK:(j + 1) * CHUNK], 9)
            c += bytes(-len(c) & 3)
            if len(c) + 0x4000 < size:
                out[off:off + len(c)] = c
                struct.pack_into('<II', out, 4 + j * 8, off, len(c))
                holes.append([off + len(c), size - len(c)])
        if fit:
            h = min(fit, key=lambda h: h[1])
            out[h[0]:h[0] + len(comp)] = comp
            struct.pack_into('<II', out, 4 + i * 8, h[0], len(comp))
            h[0] += len(comp)
            h[1] -= len(comp)
        else:
            struct.pack_into('<II', out, 4 + i * 8, len(out), len(comp))
            out += comp
            moved += 1
    if moved:
        print('track: %d chunks did not fit any free slot and went to the end' % moved)
    return bytes(out)


def is_track(name, data):
    return name.lower().endswith('.bin') and len(data) > 12 and \
        struct.unpack_from('<I', data, 4)[0] == 4 + struct.unpack_from('<I', data, 0)[0] * 8


def unpack(content, key, outdir):
    header, files = parse(xor(open(content, 'rb').read(), open(key, 'rb').read()))
    os.makedirs(os.path.join(outdir, 'files'), exist_ok=True)
    open(os.path.join(outdir, 'header.bin'), 'wb').write(header)
    open(os.path.join(outdir, 'order.txt'), 'w').write('\n'.join(n for n, _ in files) + '\n')
    for name, data in files:
        open(os.path.join(outdir, 'files', name), 'wb').write(data)
        if is_track(name, data):
            open(os.path.join(outdir, name[:-4] + '.iso'), 'wb').write(track_unpack(data))
        print(f'{len(data):10d} {name}')


def pack(indir, key, content, tracks=None):
    """tracks: {name: raw bytes} replaces data tracks (recompressed)."""
    header = open(os.path.join(indir, 'header.bin'), 'rb').read()
    files = []
    for name in open(os.path.join(indir, 'order.txt')).read().split():
        data = open(os.path.join(indir, 'files', name), 'rb').read()
        if tracks and name in tracks:
            orig = data
            data = track_pack(tracks[name], data, track_unpack(data))
            # the XOR key repeats every 512 bytes: if the track grew, grow it by a multiple of 512 (after 32-byte file
            # alignment) so every later file keeps its encrypted bytes and the patch only has to shift them
            grow = ((len(data) + 31) & -32) - ((len(orig) + 31) & -32)
            if grow:
                data += bytes((-grow & 511) + (-len(data) & 31))
        files.append((name, data))
    open(content, 'wb').write(xor(build(header, files), open(key, 'rb').read()))


def test(content, key):
    enc = open(content, 'rb').read()
    k = open(key, 'rb').read()
    plain = xor(enc, k)
    header, files = parse(plain)
    assert build(header, files) == plain, 'container rebuild differs'
    assert xor(plain, k) == enc
    for name, data in files:
        if is_track(name, data):
            raw = track_unpack(data)
            assert track_pack(raw, data, raw) == data, name + ': track repack differs'
            fresh = track_pack(raw)
            print(name, len(raw), 'fresh recompress identical:', fresh == data)
    print('identity ok')


if __name__ == '__main__':
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == 'pack' and len(a) == 4:
        pack(a[0], a[1], a[2], {'HCD1022_02.bin': open(a[3], 'rb').read()})
    else:
        {'unpack': unpack, 'pack': pack, 'test': test}[cmd](*a)
