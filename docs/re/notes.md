# Reverse-engineering notes (all verified in Mesen unless marked "guess")

## PSP container
- `rom/tm2.iso` = Sony's PC Engine emulator shell only. Game = `rom/NPJJ30036/CONTENT.DAT` (+ `PSP-KEY.EDAT`, 16-byte key).
- CONTENT.DAT: byte i XOR key[i&15] XOR public.key[i&511]. Inside: 0x80 header (file count at 0x28), 0x50-byte entries
  (name[0x40], u32 offset, u32 size), files padded to 32 with leftover bytes (kept for identity).
- Files: `HCD1022.hcd` (track list), `HCD1022_02.bin` (data track: u32 count, [u32 offset, u32 size] per 0x40000-byte zlib chunk),
  `*.at3` audio, `SYSCARD3P.PCE` (384K; first 256K = Super System Card 3.0), manual PNGs, GIMs.
- `tools/content.py` unpack/pack/test. Unchanged zlib chunks are reused, edited ones recompressed (level 9 is NOT byte-identical to Sony's).

## Disc (data track, 2048-byte sectors, `work/content/HCD1022_02.iso`; iso sector = LBA - 3596)
- No filesystem. Sector 0-1 IPL, 2-19 boot program (installs resident routines in work RAM $3800-$3DFF).
- Main program: sectors 130-196, loaded raw at bank 0x69 (CPU $4000 = bank 0x69, $6000 = 0x6A while running the field).
  iso offset = 0x41000 + (bank-0x69)*0x2000 + offset. Field menu strings at iso 0x4570d (plain SJIS).
- A copy of the first ~4 MB of the track sits at iso 0x8000000 (patch both; guess: read-error fallback).
- Sectors 2050-2125: field event/message block for the start area, loaded raw: sector 2050 -> bank 0x74, continuing through
  0x7F then CD RAM banks 0x80-0x86.
- Sectors 2146-2177: house map graphics: u16 word count, then LZ stream, streamed from CD straight to VRAM.
- 52-59 MB: MS-DOS leftovers (not game text).

## Compression (`tools/lz.py`, matches the resident routine at $3C8D / vector $3833; init $3C77 / vector $3830, A:X = source)
Flag byte MSB first, 1 = literal, 0 = match (1 byte absolute position in a 256-byte ring, zero-filled, write pos 0xEF;
length nibble + 2, nibbles two per byte, high first, taken from the same byte stream). No length header: the consumer decides
when to stop. A second ring ($3D52/$3D62, vectors $3854/$3857) is used for graphics with bit 15 of the count set.

## Text
- Encoding: 1-byte codes 0xA6-0xDF = hiragana (half-width-kana order: wo, small a..., a, i, u...), 0xA0 = space,
  SJIS 2-byte for kanji, ASCII-range bytes = voiced kana etc. (table still to dump), 0x0D newline, 0x1F xx = prefix code,
  0x12 0x00 seen at message end. Main-program strings (shops, menus) use the same mixed encoding, uncompressed.
- Dialogue: each message is its own LZ stream inside the area's event block; the text printer pulls bytes one at a time.
  First house message (mother at the door): stream at CPU $8611 with bank 0x76 at $8000 = iso 0x404E11; caller of the LZ init = $7E80.
- Font: 12x12-ish kanji drawn into BG tiles (System Card font, guess).

## Emulator harness
- `tools/mkcue.py` builds work/cd/tm2.cue (silent audio). `tools/pce.py` = headless Mesen (`--state-in`, `--route`, `--dump`, `--script`).
- States: `work/states/preload.mss` (frame 14300, just before the house map loads), `house.mss` (frame 16000, in control).
- Route to the first dialogue from house.mss: `20:down*100;130:left*8;150:down*30` (walking into the doorway triggers the mother).
- `tools/lua/lztrace.lua` logs every LZ stream (source, bank, caller, bytes pulled); `loadtrace.lua` = PC histogram + RAM dumps.
- MPR while in the field: mpr0=FF mpr1=F8 mpr2=69 mpr3=6A mpr4-6=80-82 (message code swaps mpr4), mpr7=00.
- RAM dump layout (pce.py --dump): 0x2000 work RAM (CPU $2000), 0x10000 CD RAM (banks 0x80-0x87), 0x30000 Super CD RAM (banks 0x68-0x7F).

## Message system (bank 0x6F at $6000 while a message runs; traced 2026-11-19)
- Event block = module loaded raw at base bank `$4F` (0x74 for the start area), also mapped at $6000 as code. Header: 3-byte
  entries `[bank delta, lo, hi]` (far pointer = bank `$4F`+delta, $8000 | 13-bit offset); entries 0-2 are `JMP`s
  (signature `4C 15 60 4C 16 60 4C 15 60`), entry 4 = message group table (start area: block+0x1FDB), entry 5/6 other data.
  Selector: `$485E` (A = entry index) sets `$50` (bank) and `$53/$54` (pointer).
- Group table: u16 far offsets (value>>13 = bank delta, &0x1FFF = offset), 61 entries in the start block, indexed by `$DA`.
  Group 1 = dictionary: plain NUL-terminated strings (106 words), used by code `1F nn` (word nn, 1-based).
  Every other group = one LZ stream holding several NUL-terminated messages; message k is reached by skipping k NULs.
  Groups can share a stream (equal offsets). The stream has no end marker: it ends where the next stream starts.
- `$7E6D` opens (group `$DA`, message A), `$7E5C` gets a byte, `$7E95` pre-expands into a buffer at `($97)` (about $E66E):
  bytes >= 0x20 are copied; control codes via the table at `$7EBD`:
  00 end (or return from a dictionary word), 0D newline, 02/03/10/11/14/15 = code + ASCII decimal argument (stored as code, byte),
  12 = wait, 16/17/18 -> 10 with 0 / [$3211] / 1, 19 -> 1D + number, 1C -> 1E + number, 1D -> 11 3C, 1E = money amount,
  1F nn = dictionary word, others copied as is. The drawing stage that consumes the buffer is not disassembled yet.
- The DS script matches message for message: DS `wa1/vaa1.scs#0` == start block group 0x11 message 0, same text and the same
  control codes (DS `{0012}` = byte 0x12, `{0010}{0002}` = `10` + "2"). DS file names follow the PC Engine overlay names (wa1...).
- Group 2 of the start block = 238 item names (plain names, 0E/0F and `1F` codes inside).
- Character table still incomplete: ASCII-range bytes are voiced kana and frequent kanji/katakana ('a' = が, 'd' = げ, ...).
  Derive it by aligning decoded messages with the DS Japanese text, or from the drawing routine.
