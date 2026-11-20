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

## Map loads and warping (traced 2026-11-20; `tools/lua/cdtrace.lua`, `tools/debug/warp.lua`)
- Location = area `$2BF4`, sub `$2BF5`, entrance `$2BF6`, plus `$323B`. Area = event block: resident `$3803` (A = area) reads
  sector `area*128 + 2` (count from the table at `$2616,Y`) to bank 0x74+; `$2C00` = area now loaded (no read if equal).
  Sub = the map (graphics) inside the area; entrance = spawn point (0x46 = return to the place saved in `$2BF7`/`$2BF8`, 0x18 special).
  Start: area 0x10, sub 0x11 (house), entrance 0x26. Area 0x10 sub 0x12 = overworld around the first village; sub 0x10 = the opening.
- Every map change starts a task at 6A:`$6917` (created by 6A:`$690B`: `JSR $4C9E` + inline `93 20 17 69`, `$3815` = new task);
  it reads the destination at 6A:`$697A`. Script opcodes that warp: 6F:`$7839` (area, sub, entrance), 6F:`$6784` (sub, entrance,
  `$323B`), 6F:`$67E5` (saved place `$2BF9`-`$2BFB`), all through 6A:`$6902` (A/X/Y = area/sub/entrance).
  Setting the variables and the `$9C`/`$9E` bit 4 flags from outside does nothing: the task must be created.
- `$E033` calls in the loader are AD_TRANS (area sound, 0x20 sectors at block + 0x60 sectors), not text.
- Random battles happen on the overworld with no `$E009` read. In a battle mpr4 = 0x6A (never on the field).
- Text speed: `$E3C8` = 0 draws with no per-glyph delay. Wait code `12` is handled at 69:`$52D3`; the interpreter loop
  ends at 69:`$51BF` when it reads 00.

## Battle text (traced 2026-11-20, sixth session; viewer = `tools/debug/show.py --battle`)
- Battle lines are NOT the modules' group 11. Each area has a 64K ADPCM image at sectors `area*128 + 98` .. `+129` (loaded by
  AD_TRANS; its head is map graphics). At image offset 0xF400 (iso `area*0x40000 + 0x40400`) sits one LZ stream of 235
  NUL-terminated messages, 0x994 bytes of the 0xC00 up to the end of ADPCM RAM, identical in 370 areas (4, 5, 7, 16 ... 767).
- Opener 71:`$74EE` (A = message number): `$384B` A=1 switches the LZ byte source to AD_READ (`$3D25`: 256 bytes at a time
  from ADPCM address `$28/$29` into `$2AE3`), source `$F400` is hard-coded at 71:`$7502`, then it skips A NULs and
  pre-expands through 6F:`$7E9F` into `$E66E`. Same interpreter as dialogue (wait `$52D3`, end `$51BF`).
- Codes in that stream: `19` + ASCII digit 1-4 = name placeholder (131 / 81 / 18 / 2 uses), `1B` = number, `0D` newline
  (111 messages), no wait code. Message 0 = `19 31 C9 8D55 8C82 21` (name + の攻撃!).
- A second path at 71:`$752A` (`$F65B` = FF) prints a string from the pointer `$F659/$F65A`, where `24 3x` = name
  placeholder x and `24 6E` = newline. Guess: that is what the modules' group 11 (`$0の紅丸斬$n...`, three variants) feeds.
- Command cursor: `$2805` (copy `$282B`), 0-8 row-major over 3 columns (0 = Fight). It wraps in both directions.
- The battle window wraps by itself at the window edge (28 tiles, mid-word) and shows 3 lines.
- The handler of a decimal-argument code (`19 n`, and `02 03 10 11 14 15`) reads the byte after its digits itself, past
  the dictionary hook at 6F:`$7EA8`: a one-byte dictionary code there is copied raw and drawn as a kanji lead byte
  (seen: `19 31 86` -> `1D 01 86`). insert.py keeps that byte plain.
- The stream ends with the ADPCM image, so a longer one starts earlier: 56 bytes of FF padding sit before it in the
  tightest copy (871 in most). insert.py moves the start and patches the address at 71:`$7502` (`LDA #$F4 / LDX #$00`).

## Message system (bank 0x6F at $6000 while a message runs; traced 2026-11-19)
- Event block = module loaded raw at base bank `$4F` (0x74 for the start area), also mapped at $6000 as code. Header: 3-byte
  entries `[bank delta, lo, hi]` = block offset delta*0x2000 + the plain 16-bit lo/hi (do NOT mask it to 13 or 15 bits:
  two modules have the table past 0x8000); entries 0-2 are `JMP`s into $6000-$7FFF whose targets vary by module
  (`4C 15 60 4C 16 60 4C 15 60` is only the most common), entry 4 = message group table (start area: block+0x1FDB),
  entry 5/6 other data. 203 sector-aligned modules match; the 189 with text all carry the same 106-word dictionary.
  Selector: `$485E` (A = entry index) sets `$50` (bank) and `$53/$54` (pointer).
- Group table: u16 block offsets, not sorted, indexed by `$DA` (53 entries in the start block). It can sit before or after
  the streams and ends at a `00 01 02 .. 0F` byte ramp, at FF padding, or where the dictionary starts.
  Groups 2-13 are the same system text in every module (item names, battle and menu messages); 14+ are the area's own.
  `1F nn` is expanded at byte level: a word can supply the trail byte of a kanji (`8F 1F 47` -> `8F 4D C9`).
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
- Character table: learned by `tools/align.py` from the DS script (`work/script/table.json`, keys = mode letter h/k + byte,
  or an SJIS pair). 0x21-0x60 and 0x7A-0x7F = frequent kanji and signs, 0x30-0x39 = full-width digits, 0x61-0x79 = が..ぽ,
  0xA1-0xDF = kana; `0E`/`0F` = katakana/hiragana for the kana ranges only. 0x20 unknown. Not yet confirmed by the drawing routine.

## Text drawing (traced 2026-11-19, third session; `tools/lua/vdcwho.lua`, `drawtrace.lua`, `poketext.lua`)
- Main program = banks 0x69-0x72 only (resident, identical to the disc at runtime). Banks 0x73+ are overwritten by area data.
  Free and resident: 6E +1EB9 (327 bytes), 6A +1F67 (153), 6D +1FCC (52), 72 +1FEF (17).
- Interpreter of the expanded buffer (`($95)`, about $E66E): main `$51A1` loop, `$51CD` get byte, `$51D6` dispatch.
  Control codes < 0x20: jump table at `$5215` (word per code). SJIS lead byte (80-9F, E0+) = 2-byte character -> 12x12
  (`$5264`) or, in text mode 2, 8x12 (`$5272`). 1-byte characters (20-7F, A0-DF): jump table at `$5256` by text mode
  (`$E3CC` & 3): 0 = `$525E` (game table -> SJIS -> 12x12), 1 = `$526B` (8x8 half-width), 2 = `$5272`, 3 = `$5279` (4-px digits).
  Codes `04`-`07` select text mode 0-3; `02 n` / `03 n` set cursor x / y; `08`-`0B` = x+1, x-1, y+1, ...; `0D` newline (6D:$6644).
- Far calls: `JSR $492D` + 3 inline bytes (`BIT target`) = call into bank 6D mapped at $6000 (`$4933` = 6E ... `$494B` = 72).
- Bank 6D (mapped at $6000 by the far call) holds the drawing code:
  `$6000` 12x12 (glyph via `$620D`: 16 custom glyphs at `$667C`/`$668C`, else System Card EX_GETFNT), `$625A` 8x8
  (glyph via `$62FF`: 14 custom glyphs `0-9 _ ^ ]` + DE at `$674C`/`$675A`, else System Card bank 1 font at `$8000 + ch*8`,
  i.e. SYSCARD3P.PCE 0x2000 + ch*8: plain ASCII), `$63E2` 8x12, `$636F` 4x8.
  Glyph buffer `$31E1` = 16 bits per row. Cursor `$8D`/`$8E` in 4-px units relative to the window origin `$90`/`$91` (tiles);
  window size `$92`/`$93` (tiles). A 12x12 glyph advances 3 units, 8x8 advances 2; a newline advances 4 units after a 12x12
  glyph (`$9C` bit 1) and 2 otherwise. Each window cell gets its own tile: `$612A` reads the cell's tile back (or takes a
  blank one), `$60E8` composes (AND mask, OR glyph rows), `$6177` writes it in the text colour. Shifts are 0 or 4 px only.
  `$6608` (A = width, Y = height in units) wraps / scrolls before a glyph, `$6635` advances and wraps after it.
- Text speed: one glyph every 4 frames (`$E3C8`/`$E3C9`), not changed yet.
- English works with no code at all: `05` + ASCII draws 8-px fixed-width text (28 characters per line, 8-px lines).

## VWF (`src/vwf.s`, built and applied by `tools/build.py`; verified from a cold boot)
- 6D:$625D (inside the 8x8 entry) -> stub in the 6D tail -> routine in the 6E tail mapped at $8000. It reuses the stock glyph
  fetch and two-tile blitter with OR masks, shifts by the pixel remainder, and advances by a per-character width
  (table measured from the glyph bitmaps by `build.py`: left trim << 4 | advance). Sets `$9C` bit 1: 16-px lines.
- Result: 3 lines per page as in Japanese, about 37 characters per line. Usable line width = 216 px (the routine asks for
  two free tiles; the dialogue window is 28 tiles wide).
- `build.py --all-ascii` (verified from a cold boot) points text modes 0/2/3 at the half-width path so messages need no `05` prefix.
- Savestates hold the old program: `work/states-en/house.mss` is the cold-boot state of the patched build.
