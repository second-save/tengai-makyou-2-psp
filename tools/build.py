#!/usr/bin/env python3
"""Build the patched data track: assemble src/vwf.s and apply the engine patches.

  build.py ORIG.iso SYSCARD.PCE OUT.iso [--all-ascii]     -> OUT.iso and OUT.iso.writes (log for romdiff.py --writes)

--all-ascii: 1-byte characters draw through the half-width path in every text mode (no 05 prefix needed) and
message bytes 0x80-0xFF become one-byte dictionary codes: the build for tools/insert.py, Japanese text no longer reads.
Needs ca65/ld65 (cc65). Every write is checked against the original bytes and mirrored to the second disc copy.
"""
import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = 0x41000          # iso offset of bank 0x69 (main program, banks 0x69-0x72 stay resident)
MIRROR = 0x8000000      # second copy of the start of the track
DIGITS = bytes(range(0x30, 0x3A)) + b'_^]\xde'   # 6D:$674C: characters with the game's own 8x8 glyphs at 6D:$675A


SLOT2 = ('Sword', 'Arts', 'Skills', 'Demon')   # 剣法 秘芸 体術 鬼道 (DS names), 6 bytes each at most


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
    stub, vwf, dic = (open(tmp + '/vwf.' + s, 'rb').read() for s in ('stub', 'vwf', 'dict'))
    vwf = vwf[:-96] + widths(iso, card)
    writes = [
        (far(0x6D, 0x7FCC, 0x6000), stub, 'vwf stub'),
        (far(0x6E, 0x9EB9, 0x8000), vwf, 'vwf + width table'),
        (far(0x69, 0x5FE6, 0x4000), dic, 'dictionary code routine'),
        # 6D:$625D (after PHA PHX PHY): JSR stub; JMP $6014 (PLY PLX PLA RTS)
        (far(0x6D, 0x625D, 0x6000), bytes.fromhex('20cc7f4c1460'), 'half-width draw -> vwf'),
    ]
    if all_ascii:
        # 6F:$7EA8 JSR $7E5C (next message byte) -> bytes 0x80-0xFF expand as dictionary words (tools/insert.py)
        writes.append((far(0x6F, 0x7EA8, 0x6000), bytes.fromhex('20e65f'), 'message byte -> dictionary codes'))
        # main $5256: handler table for 1-byte characters by text mode; point modes 0, 2, 3 at mode 1's far call ($526B)
        writes += [(far(0x69, 0x5256 + m * 2, 0x4000), bytes.fromhex('6b52'), 'text mode %d -> half-width' % m) for m in (0, 2, 3)]
        # battle command menu, slot 2 = the actor's technique class: 70:$7646 copied 4 bytes from a 4-byte table at
        # $76CB into the menu string at $7759; now 6 bytes from an 8-byte table in bank 70's own free tail ($7FDE; 6A is
        # not mapped when this runs). TXA ASL ASL ASL TAY LDX #$FA / LDA $7FDE,Y STA $765F,X INY INX BNE / RTS (same 18 bytes)
        writes.append((far(0x70, 0x7646, 0x6000), bytes.fromhex('8a0a0a0aa8a2fab9de7f9d5f76c8e8d0f660'), 'menu slot 2: 6-byte names'))
        # field menu: its English does not fit the 43 bytes at 6B:$6705, so 6B:$665B (JSR $50A3 / BIT $6705: print the
        # string inline) becomes a far call into 6E ($4933) that prints a copy at 6E:$7FB3 (written by mainstr.py)
        writes.append((far(0x6B, 0x665B, 0x6000), bytes.fromhex('2033492cac7f'), 'field menu: far call'))
        writes.append((far(0x6E, 0x7FAC, 0x6000), bytes.fromhex('20a3502cb37f60'), 'field menu: print from 6E'))
        writes.append((far(0x70, 0x7FDE, 0x6000), b''.join(n.ljust(8).encode() for n in SLOT2), 'menu slot 2 names'))
    new, log = bytearray(iso), []
    for off, data, name in writes:
        for o in (off, off + MIRROR):
            assert iso[o:o + len(data)] == iso[off:off + len(data)], 'mirror differs at %x' % o
            log.append('%x %s %s %s' % (o, iso[o:o + len(data)].hex(), data.hex(), name))
            new[o:o + len(data)] = data
    for off, data, name in writes[:3] + [w for w in writes if w[2] in ('menu slot 2 names', 'field menu: print from 6E')]:
        assert set(iso[off:off + len(data)]) == {0xFF}, name + ': target is not free space'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(new)
    open(out + '.writes', 'w').write('\n'.join(log) + '\n')
    assert len(vwf) <= 0xF3, 'vwf runs into the field menu routine at 6E:$7FAC'
    print('vwf %d bytes (room %d), stub %d (room %d), %d writes' % (len(vwf), 0xF3, len(stub), 0x34, len(log)))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a, all_ascii='--all-ascii' in sys.argv)
