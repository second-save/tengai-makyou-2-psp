#!/usr/bin/env python3
"""Build the patched data track: assemble src/vwf.s and apply the engine patches.

  build.py ORIG.iso SYSCARD.PCE OUT.iso [--all-ascii]     -> OUT.iso and OUT.iso.writes (log for romdiff.py --writes)

--all-ascii: 1-byte characters draw through the half-width path in every text mode (no 05 prefix needed).
Needs ca65/ld65 (cc65). Every write is checked against the original bytes and mirrored to the second disc copy.
"""
import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = 0x41000          # iso offset of bank 0x69 (main program, banks 0x69-0x72 stay resident)
MIRROR = 0x8000000      # second copy of the start of the track
DIGITS = bytes(range(0x30, 0x3A)) + b'_^]\xde'   # 6D:$674C: characters with the game's own 8x8 glyphs at 6D:$675A


def far(bank, cpu, base):
    """iso offset of CPU address `cpu` in main-program `bank` mapped at `base`."""
    return MAIN + (bank - 0x69) * 0x2000 + cpu - base


def widths(iso, syscard):
    """(left trim << 4 | advance) per character 0x20-0x7F, measured on the 8 glyph rows."""
    assert iso[far(0x6D, 0x674C, 0x6000):][:14] == DIGITS
    out = bytearray()
    for c in range(0x20, 0x80):
        i = DIGITS.find(c)
        rows = iso[far(0x6D, 0x675A, 0x6000) + i * 8:][:8] if i >= 0 else syscard[0x2000 + c * 8:][:8]
        ink = 0
        for r in rows:
            ink |= r
        if not ink:
            out.append(0x04)                      # space
            continue
        left = 8 - ink.bit_length()
        right = (ink & -ink).bit_length() - 1     # blank columns on the right
        out.append(left << 4 | min(8 - left - right + 1, 8))
    return bytes(out)


def main(orig, syscard, out, all_ascii=False):
    iso = open(orig, 'rb').read()
    card = open(syscard, 'rb').read()
    tmp = os.path.join(ROOT, 'build', 'obj')
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(['ca65', '--cpu', 'huc6280', os.path.join(ROOT, 'src/vwf.s'), '-o', tmp + '/vwf.o'], check=True)
    subprocess.run(['ld65', '-C', os.path.join(ROOT, 'src/vwf.cfg'), tmp + '/vwf.o', '-o', tmp + '/vwf'], check=True)
    stub, vwf = (open(tmp + '/vwf.' + s, 'rb').read() for s in ('stub', 'vwf'))
    vwf = vwf[:-96] + widths(iso, card)
    writes = [
        (far(0x6D, 0x7FCC, 0x6000), stub, 'vwf stub'),
        (far(0x6E, 0x9EB9, 0x8000), vwf, 'vwf + width table'),
        # 6D:$625D (after PHA PHX PHY): JSR stub; JMP $6014 (PLY PLX PLA RTS)
        (far(0x6D, 0x625D, 0x6000), bytes.fromhex('20cc7f4c1460'), 'half-width draw -> vwf'),
    ]
    if all_ascii:
        # main $5256: handler table for 1-byte characters by text mode; point modes 0, 2, 3 at mode 1's far call ($526B)
        writes += [(far(0x69, 0x5256 + m * 2, 0x4000), bytes.fromhex('6b52'), 'text mode %d -> half-width' % m) for m in (0, 2, 3)]
    new, log = bytearray(iso), []
    for off, data, name in writes:
        for o in (off, off + MIRROR):
            assert iso[o:o + len(data)] == iso[off:off + len(data)], 'mirror differs at %x' % o
            log.append('%x %s %s %s' % (o, iso[o:o + len(data)].hex(), data.hex(), name))
            new[o:o + len(data)] = data
    for off, data, name in writes[:2]:
        assert set(iso[off:off + len(data)]) == {0xFF}, name + ': target is not free space'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(new)
    open(out + '.writes', 'w').write('\n'.join(log) + '\n')
    print('vwf %d bytes (room %d), stub %d (room %d), %d writes' % (len(vwf), 0x147, len(stub), 0x34, len(log)))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a, all_ascii='--all-ascii' in sys.argv)
