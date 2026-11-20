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


LABELS = (('#.......', '#.......', '#...#.#.', '#...#.#.', '#...#.#.', '#....#..', '###..#..', '........'),   # _ Lv
          ('###.##..', '.#..#.#.', '.#..#.#.', '.#..##..', '.#..#...', '.#..#...', '.#..#...', '........'),   # ^ TP
          ('#.#.##..', '#.#.#.#.', '#.#.#.#.', '###.##..', '#.#.#...', '#.#.#...', '#.#.#...', '........'))   # ] HP


def glyph(rows):
    return bytes(int(r.replace('#', '1').replace('.', '0'), 2) for r in rows)


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
        # 6D:$625D (after PHA PHX PHY): JSR stub; JMP $6014 (PLY PLX PLA RTS)
        (far(0x6D, 0x625D, 0x6000), bytes.fromhex('20cc7f4c1460'), 'half-width draw -> vwf'),
    ]
    if all_ascii:
        # 6F:$7EA8 JSR $7E5C (next message byte) -> bytes 0x80-0xFF expand as dictionary words (tools/insert.py)
        # (the hook, src/vwf.s DICT, is position-independent; it lives at 6F:$7FF0, in the store routine rewritten below)
        writes.append((far(0x6F, 0x7EA8, 0x6000), bytes.fromhex('20f07f'), 'message byte -> dictionary codes'))
        # main $5256: handler table for 1-byte characters by text mode; point modes 0, 2, 3 at mode 1's far call ($526B)
        writes += [(far(0x69, 0x5256 + m * 2, 0x4000), bytes.fromhex('6b52'), 'text mode %d -> half-width' % m) for m in (0, 2, 3)]
        # battle command menu, slot 2 = the actor's technique class: 70:$7646 copied 4 bytes from a 4-byte table at
        # $76CB into the menu string at $7759; now 6 bytes from an 8-byte table in bank 70's own free tail ($7FDE; 6A is
        # not mapped when this runs). TXA ASL ASL ASL TAY LDX #$FA / LDA $7FDE,Y STA $765F,X INY INX BNE / RTS (same 18 bytes)
        writes.append((far(0x70, 0x7646, 0x6000), bytes.fromhex('8a0a0a0aa8a2fab9de7f9d5f76c8e8d0f660'), 'menu slot 2: 6-byte names'))
        # field menu: its English does not fit the 43 bytes at 6B:$6705, so 6B:$665B (JSR $50A3 / BIT $6705: print the
        # string inline) becomes a far call into 6E ($4933) that prints a copy at 6E:$7FBF (written by mainstr.py)
        writes.append((far(0x6B, 0x665B, 0x6000), bytes.fromhex('2033492cb87f'), 'field menu: far call'))
        writes.append((far(0x6E, 0x7FB8, 0x6000), bytes.fromhex('20a3502cbf7f60'), 'field menu: print from 6E'))
        # the kind names ({1A} in "Use which ...": 武具 道具 巻物 ...) are looked up by number from the list whose base is
        # set at 6B:$6D7B (LDY #$6B / LDX #$99); it moves into the old field menu string at 6B:$6705 (unused now,
        # English list written there by mainstr.py)
        # (6B:$6CE0 = JSR $4661: the A-th string of the list at Y:X). Every base that pointed into it moves:
        writes.append((far(0x6B, 0x6D7B, 0x6000), bytes.fromhex('a067a205'), 'kind name list -> 6B:$6705'))
        writes.append((far(0x6B, 0x6CF8, 0x6000), bytes.fromhex('a067a205'), 'kind name list -> 6B:$6705 (2)'))
        writes.append((far(0x6B, 0x6D10, 0x6000), bytes.fromhex('a067a21b'), 'technique kind list -> 6B:$671B'))
        writes.append((far(0x6B, 0x6D75, 0x6000), bytes.fromhex('a067a21b'), 'technique kind list -> 6B:$671B (2)'))
        # party names (卍丸 カブキ 極楽 絹 シロ at 6B:$6C3D, base at 6B:$6CDC) move into the 37 bytes the old kind list
        # freed at 6B:$6B99 (English written there by mainstr.py)
        writes.append((far(0x6B, 0x6CDC, 0x6000), bytes.fromhex('a06ba299'), 'party name list -> 6B:$6B99'))
        # second party name list (status bar; 6B:$6C55, base at 6B:$6CD3) moves to 6B:$6C3D, where it and the old first
        # list leave 44 bytes
        writes.append((far(0x6B, 0x6CD3, 0x6000), bytes.fromhex('a06ca23d'), 'party name list 2 -> 6B:$6C3D'))
        # the same two lists through the second base table (6B:$6D81 / $6D8A, status screen)
        writes.append((far(0x6B, 0x6D84, 0x6000), bytes.fromhex('a06ca23d'), 'party name list 2 -> 6B:$6C3D (2)'))
        writes.append((far(0x6B, 0x6D8D, 0x6000), bytes.fromhex('a06ba299'), 'party name list -> 6B:$6B99 (2)'))
        # status bar: the HP / TP label sits 6 units (24 px, two kanji) after the member's column (6B:$61D1 CLC ADC #6);
        # 8 units leave 32 px for the short names of list 2 (user ruling: shorter names where they would overflow)
        writes.append((far(0x6B, 0x61D2, 0x6000), bytes.fromhex('6908'), 'status bar: name room 24 -> 32 px'))
        # field menu money window ({1B}両 at 6B:$62A7, printed by 6B:$62A0 JSR $50A3 / BIT $62A7, pointer at $62A4): "Ryo" needs one more
        # byte, so a copy after the second name list (6B:$6C55, written by mainstr.py) is printed instead
        writes.append((far(0x6B, 0x62A4, 0x6000), bytes.fromhex('556c'), 'money window -> 6B:$6C55'))
        # status screen: each label is copied by JSR $540C + inline pointer; 徳 (Virtue, 2 bytes at 6B:$6005, pointer at
        # 6B:$62C8) gets the full word from a copy at 6B:$6C61 (after the money window)
        writes.append((far(0x6B, 0x62C8, 0x6000), bytes.fromhex('616c'), 'Virtue label -> 6B:$6C61'))
        # long messages: the pre-expander stores each output byte through 6F:$7FC8 into the 256-byte buffer at $E66E;
        # when full, the game restarts it with "長い!" (too long), and ~340 English messages pass 256 bytes. Now the
        # buffer is drawn and emptied at every page end (wait code 12) while 6F stays mapped (a far call into 6A that
        # yielded at the key wait crashed the game). 6F:$7FD3 (after LDA #flag, the flag at $7FD2 is set for dialogue):
        # BEQ done / PLA PHA CMP #$12 BNE done / PHX PHY, save MPR4-5 (the message stream is read through them and other
        # tasks remap them during the key wait), JSR $5FE6, restore, PLY PLX / done: PLA RTS, then the dictionary hook.
        # 69:$5FE6 (always mapped): NUL-terminate at ($97), interpret from $E66E at the dialogue speed $3279 (as the
        # message task at 6F:$6534 does), reset the write pointer $97/$98 to $E66E.
        writes.append((far(0x6F, 0x7FD3, 0x6000), bytes.fromhex('f0196848c912d013da5a43104843204820e65f68532068531 07afa6860'.replace(' ', '')) + dic,
                       'message buffer: flush at page ends + dictionary hook'))
        writes.append((far(0x69, 0x5FE6, 0x4000), bytes.fromhex('629297a96e8595a9e68596ad793220e750a96e8597a9e6859860'),
                       'message buffer: draw and empty'))
        # status labels: the game's own 8x8 glyphs for '_' '^' ']' (6D:$675A + index * 8, index from the list at $674C)
        # are small kanji 段 技 体 (level, TP, HP) in the status bar; redrawn as Lv, TP, HP (rows 0-6, as the digits)
        writes.append((far(0x6D, 0x675A + 10 * 8, 0x6000), b''.join(glyph(g) for g in LABELS), 'status labels Lv TP HP'))
        writes.append((far(0x70, 0x7FDE, 0x6000), b''.join(n.ljust(8).encode() for n in SLOT2), 'menu slot 2 names'))
    # original bytes each code patch must replace (catches an address off by one)
    expect = {'money window -> 6B:$6C55': 'a762', 'Virtue label -> 6B:$6C61': '0560', 'field menu: far call': '20a3502c0567',
              'kind name list -> 6B:$6705': 'a06ba299', 'kind name list -> 6B:$6705 (2)': 'a06ba299',
              'technique kind list -> 6B:$671B': 'a06ba2ac', 'technique kind list -> 6B:$671B (2)': 'a06ba2ac',
              'party name list -> 6B:$6B99': 'a06ca23d', 'party name list 2 -> 6B:$6C3D': 'a06ca255', 'party name list 2 -> 6B:$6C3D (2)': 'a06ca255',
              'party name list -> 6B:$6B99 (2)': 'a06ca23d',
              'status bar: name room 24 -> 32 px': '6906', 'menu slot 2: 6-byte names': '8a0a0aa882b9cb769d5977c8e8e00490f460',
              'message byte -> dictionary codes': '205c7e', 'half-width draw -> vwf': None}
    for off, data, name in writes:
        if expect.get(name):
            assert iso[off:off + len(data)].hex() == expect[name], '%s: original bytes %s' % (name, iso[off:off + len(data)].hex())
    new, log = bytearray(iso), []
    for off, data, name in writes:
        for o in (off, off + MIRROR):
            assert iso[o:o + len(data)] == iso[off:off + len(data)], 'mirror differs at %x' % o
            log.append('%x %s %s %s' % (o, iso[o:o + len(data)].hex(), data.hex(), name))
            new[o:o + len(data)] = data
    for off, data, name in writes[:2] + [w for w in writes if w[2] in ('menu slot 2 names', 'field menu: print from 6E',
                                                                       'message buffer: draw and empty')]:
        assert set(iso[off:off + len(data)]) == {0xFF}, name + ': target is not free space'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(new)
    open(out + '.writes', 'w').write('\n'.join(log) + '\n')
    assert len(vwf) <= 0xFF, 'vwf runs into the field menu routine at 6E:$7FB8'
    print('vwf %d bytes (room %d), stub %d (room %d), %d writes' % (len(vwf), 0xFF, len(stub), 0x34, len(log)))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a, all_ascii='--all-ascii' in sys.argv)
