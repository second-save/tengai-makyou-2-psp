#!/usr/bin/env python3
"""HuC6280 disassembler (full opcode table).

    dis6280.py FILE FILE_OFFSET CPU_ADDR [COUNT]      disassemble COUNT instructions
    dis6280.py --lba LBA[:OFF] CPU_ADDR [COUNT]        same, from work/tm2_02.iso (real LBA, pregap removed)
"""
import sys
from pathlib import Path

ISO = Path(__file__).resolve().parent.parent / "work" / "tm2_02.iso"
PREGAP = 0xE6  # work/tm2_02.iso starts 0xE6 sectors before LBA 0 (track pregap)

# mode -> (operand bytes, format)
M = {
    "imp": (0, ""), "acc": (0, "A"), "imm": (1, "#${0:02X}"), "zp": (1, "${0:02X}"),
    "zpx": (1, "${0:02X},X"), "zpy": (1, "${0:02X},Y"), "abs": (2, "${0:04X}"),
    "abx": (2, "${0:04X},X"), "aby": (2, "${0:04X},Y"), "ind": (2, "(${0:04X})"),
    "iax": (2, "(${0:04X},X)"), "izx": (1, "(${0:02X},X)"), "izy": (1, "(${0:02X}),Y"),
    "izp": (1, "(${0:02X})"), "rel": (1, None), "zpr": (2, None), "blk": (6, None),
    "imzp": (2, "#${0:02X},${1:02X}"), "imzx": (2, "#${0:02X},${1:02X},X"),
    "imab": (3, None), "imax": (3, None),
}

T = """00 BRK imp|01 ORA izx|02 SXY imp|03 ST0 imm|04 TSB zp|05 ORA zp|06 ASL zp|07 RMB0 zp|08 PHP imp|09 ORA imm|0A ASL acc|0C TSB abs|0D ORA abs|0E ASL abs|0F BBR0 zpr
10 BPL rel|11 ORA izy|12 ORA izp|13 ST1 imm|14 TRB zp|15 ORA zpx|16 ASL zpx|17 RMB1 zp|18 CLC imp|19 ORA aby|1A INC acc|1C TRB abs|1D ORA abx|1E ASL abx|1F BBR1 zpr
20 JSR abs|21 AND izx|22 SAX imp|23 ST2 imm|24 BIT zp|25 AND zp|26 ROL zp|27 RMB2 zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs|2E ROL abs|2F BBR2 zpr
30 BMI rel|31 AND izy|32 AND izp|34 BIT zpx|35 AND zpx|36 ROL zpx|37 RMB3 zp|38 SEC imp|39 AND aby|3A DEC acc|3C BIT abx|3D AND abx|3E ROL abx|3F BBR3 zpr
40 RTI imp|41 EOR izx|42 SAY imp|43 TMA imm|44 BSR rel|45 EOR zp|46 LSR zp|47 RMB4 zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs|4F BBR4 zpr
50 BVC rel|51 EOR izy|52 EOR izp|53 TAM imm|54 CSL imp|55 EOR zpx|56 LSR zpx|57 RMB5 zp|58 CLI imp|59 EOR aby|5A PHY imp|5D EOR abx|5E LSR abx|5F BBR5 zpr
60 RTS imp|61 ADC izx|62 CLA imp|64 STZ zp|65 ADC zp|66 ROR zp|67 RMB6 zp|68 PLA imp|69 ADC imm|6A ROR acc|6C JMP ind|6D ADC abs|6E ROR abs|6F BBR6 zpr
70 BVS rel|71 ADC izy|72 ADC izp|73 TII blk|74 STZ zpx|75 ADC zpx|76 ROR zpx|77 RMB7 zp|78 SEI imp|79 ADC aby|7A PLY imp|7C JMP iax|7D ADC abx|7E ROR abx|7F BBR7 zpr
80 BRA rel|81 STA izx|82 CLX imp|83 TST imzp|84 STY zp|85 STA zp|86 STX zp|87 SMB0 zp|88 DEY imp|89 BIT imm|8A TXA imp|8C STY abs|8D STA abs|8E STX abs|8F BBS0 zpr
90 BCC rel|91 STA izy|92 STA izp|93 TST imab|94 STY zpx|95 STA zpx|96 STX zpy|97 SMB1 zp|98 TYA imp|99 STA aby|9A TXS imp|9C STZ abs|9D STA abx|9E STZ abx|9F BBS1 zpr
A0 LDY imm|A1 LDA izx|A2 LDX imm|A3 TST imzx|A4 LDY zp|A5 LDA zp|A6 LDX zp|A7 SMB2 zp|A8 TAY imp|A9 LDA imm|AA TAX imp|AC LDY abs|AD LDA abs|AE LDX abs|AF BBS2 zpr
B0 BCS rel|B1 LDA izy|B2 LDA izp|B3 TST imax|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B7 SMB3 zp|B8 CLV imp|B9 LDA aby|BA TSX imp|BC LDY abx|BD LDA abx|BE LDX aby|BF BBS3 zpr
C0 CPY imm|C1 CMP izx|C2 CLY imp|C3 TDD blk|C4 CPY zp|C5 CMP zp|C6 DEC zp|C7 SMB4 zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs|CD CMP abs|CE DEC abs|CF BBS4 zpr
D0 BNE rel|D1 CMP izy|D2 CMP izp|D3 TIN blk|D4 CSH imp|D5 CMP zpx|D6 DEC zpx|D7 SMB5 zp|D8 CLD imp|D9 CMP aby|DA PHX imp|DD CMP abx|DE DEC abx|DF BBS5 zpr
E0 CPX imm|E1 SBC izx|E3 TIA blk|E4 CPX zp|E5 SBC zp|E6 INC zp|E7 SMB6 zp|E8 INX imp|E9 SBC imm|EA NOP imp|EC CPX abs|ED SBC abs|EE INC abs|EF BBS6 zpr
F0 BEQ rel|F1 SBC izy|F2 SBC izp|F3 TAI blk|F4 SET imp|F5 SBC zpx|F6 INC zpx|F7 SMB7 zp|F8 SED imp|F9 SBC aby|FA PLX imp|FD SBC abx|FE INC abx|FF BBS7 zpr"""
OPS = {int(e[:2], 16): e.split()[1:] for line in T.split("\n") for e in line.split("|")}


def dis_one(data, off, pc):
    """Return (length, text) for the instruction at data[off], located at CPU address pc."""
    op = data[off]
    if op not in OPS:
        return 1, f".db ${op:02X}"
    name, mode = OPS[op]
    n, fmt = M[mode]
    b = data[off + 1: off + 1 + n]
    if len(b) < n:
        return 1, f".db ${op:02X}"
    w = lambda i: b[i] | b[i + 1] << 8
    rel = lambda v, base: (base + (v - 256 if v > 127 else v)) & 0xFFFF
    if mode == "rel":
        arg = f"${rel(b[0], pc + 2):04X}"
    elif mode == "zpr":
        arg = f"${b[0]:02X},${rel(b[1], pc + 3):04X}"
    elif mode == "blk":
        arg = f"${w(0):04X},${w(2):04X},${w(4):04X}"
    elif mode in ("imab", "imax"):
        arg = f"#${b[0]:02X},${w(1):04X}" + (",X" if mode == "imax" else "")
    elif n == 2 and mode not in ("imzp", "imzx"):
        arg = fmt.format(w(0))
    else:
        arg = fmt.format(*b)
    return 1 + n, f"{name} {arg}".rstrip()


def dis(data, off, pc, count=60):
    for _ in range(count):
        if off >= len(data):
            break
        n, text = dis_one(data, off, pc)
        print(f"${pc:04X}: {data[off:off + n].hex():<14} {text}")
        off += n
        pc += n


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--lba":
        lba, _, o = a[1].partition(":")
        data, off = ISO.read_bytes(), (int(lba, 0) + PREGAP) * 2048 + int(o or "0", 0)
    else:
        data, off = Path(a[0]).read_bytes(), int(a[1], 0)
    # self-check: TII is 7 bytes, BBR is 3, unknown opcode is 1
    assert dis_one(bytes([0x73, 0, 0x20, 0, 0x30, 4, 0]), 0, 0)[0] == 7
    assert dis_one(bytes([0x0F, 0x10, 0xFD]), 0, 0x4000) == (3, "BBR0 $10,$4000")
    dis(data, off, int(a[2], 0), int(a[3], 0) if len(a) > 3 else 60)
