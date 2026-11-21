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

## Main-program strings (traced 2026-11-20, tenth session; `tools/mainstr.py`, `script/main.json`)
- UI strings are NUL-terminated, same mixed encoding as messages, printed directly (no pre-expansion, no dictionary):
  69:`$50A3` + inline pointer prints at once (text speed 0). Codes (table at 69:`$5215`): `02 x` / `03 y` = cursor
  x / y (arg & 0x7F, 4-px units from the window's inner origin), `08`-`0B` = x+1 x-1 y+1 y-1, `01` = record a choice
  position (no advance; the cursor is a highlight box), `0C` = clear window, `0D` newline, `14 n` / `15 n` = colour,
  `16 x y w h` / `18 x y w h` = open a window (tiles, bit 7 set), `17` = close, `1A` = name slot (pointer at
  `$EAD3/$EAD8`), `1B` = number, `04`-`07` = text mode.
- Wrap / scroll before a glyph: 6D:`$6608` (A = width, Y = height in units) wraps when x + A > (window w - 2) * 2.
- Name lists: 6B:`$4661` = A-th string after skipping A NULs from base Y:X; the bases are immediates in the 6B jump
  table at `$6C7E` (selectors 0x0D 0x0E 0x0F 0x10 ...) and at `$6D6F`-`$6D97`. Lists can move by patching the pair.
- Code patches strings at fixed offsets: the battle command menu (70:`$7745`: colours at +06 +48 +52, slot 2 name
  +14, slot 9 name +56). Check for `STA` into a string before changing its layout.
- `pce.py --shots` with a long list hangs; use `--shot-every`.

## Start menu panel (solved 2026-11-21, eleventh session; `tools/panel.py`, `tools/lua/vramwho.lua`)
- Bank 78 = iso 0x5F000 (+ mirror). Resource 0 (u16 size 0xD3E, u16 8, u16 tile block 0x2D, u16 map block 0xB48,
  37 bytes): tile block = u16 word count (bit 15: high bytes from ring B) + stream for 69:$4681, loaded at tile 256;
  map block = w, h (32, 32) + plain LZ (ring A) of u16 deltas, entry = running sum + $E100 (70:$6AE8, via $2DBC and
  69:$5D1C). Resource 1 at 0x5FD3E (size 0x40F): its block at +8 = 32 sprite cells, the highlighted 起 / 転 buttons
  (SAT at VRAM $0E00: two 32x64 sprites, patterns $120 / $140; the right button uses cells +8).
- Graphics LZ = two decoders (ring A $3C8D / $E000, ring B $3D62 / $E100) taking turns on ONE flag / nibble / byte
  stream: the writer fetches low byte from A, high byte from B (or A). `lz.unpack_rings` / `pack_rings`. This is
  why decoding with ring A alone (tenth session) gave data that "did not contain the tiles".
- Old notes, kept for the record:
- The panel before the title ("さいしょから はじめたいときは「起」を...") is BG tiles 258+ (BAT 64 wide), drawn with no font
  fetch. Its tiles are not raw on the disc. Loads before it: CD_READ sector 21506 x 0x60 (f=709) and 21634 x 0x73
  (f=897, banks from 6B?); LZ streams at f=1351-1396 from bank 78 ($802F 6112 bytes, $8B4A, $9157, $8D48) decode
  (ring A, assuming bank 78 = sector 21634 + 13 banks) to data that does not contain the panel tiles. Ring B inits
  (`$3D52`, logged by `tools/lua/lztrace.lua` now with A:X) show 8100/8B00/8600/8800: probably a second stage
  (graphics, count bit 15), not a source pointer. VRAM writers: BIOS 00:E5F7/E5F9 (51,200 bytes), 69:$4706/$470C.
  Next: break on VDC writes to the panel tiles' VRAM address (tile 258 * 16 words) and follow the source back.

## Programs and the ending staff roll (2026-11-21, twelfth session; `tools/debug/prog.lua`, `tools/roll.py`, `src/roll.s`)
- Resident loop 00:`$3887`: `JSR $388C` loads program A (sector A*128+2, count from `$2616,Y`, via `$3908`) to bank
  $69 (+$21) and jumps to `$4000`; the program returns the next program number in A. 0x01 = main game, 0x9E = ending
  + staff roll, 0x9F-0xA1 = intro (first call, f=63), 0xA8/0xA9 = title. `prog.lua --var PROG=0x9E` swaps the first
  load: the ending plays from a cold boot (roll from f~4300 to f~19000, clear time from boot RAM).
- Staff roll = bank $78 of program 0x9E (iso 0x279F000, mirror +0x8000000): u16 pointer table (entry 0 = $0002),
  records `colour (1 = heading) + 2-byte cells + 00 00`, a record starting `00 00` ends it. Printer 6A:`$6340`
  (pointer `$8C`), cell renderer 6A:`$64B3`: 16 cells of 16x16 per line, `$650C` = glyph: `01 nn` = own glyph from
  the table at 6A:`$6641` (0/1 = "P." "H.", 2 辻 3 濱 4 潘 5 蜷 6 茉 7 ㈱ 8 ㈲ 9 卍; `01 F0`-`F4` = clear-time digits),
  else System Card EX_GETFNT 16x16 into `$2DEE` (16 rows x 2 bytes). `src/roll.s` (6A:$7F00, FF tail) adds
  two-ASCII cells (two 8x8 glyphs, System Card bank 1 at $8000 + c*8): 32 characters per line.
- Opening card "制作・総指揮 工藤裕司" (intro program 0x9F, f 540-700; `tools/card.py`): tiles = resource
  `[flags][u16 count]` + plain LZ in intro bank 70 at $9B31 (69:$43B9 streams it to VRAM tile 0x100), map = plain
  LZ in the intro's ADPCM image (ADPCM $0000 = iso 0x27EF000 = block + 92 sectors) at $1EE2, read by 69:$4522 through
  the intro's own LZ reader (`$4216`, AD_READ 256 bytes at a time into $2BEE): 32x32 words, entry = 0x100 + running
  sum. A table read at f=270 sits at ADPCM $1FCD, right after the map (235 bytes of room). Map addresses per index:
  table at 69:$587C. The English card uses 71 tiles (count raised from 0x40); frames 0-3200 differ from the
  original only on the card. `tools/lua/adpcmdump.lua` dumps ADPCM RAM and logs AD_READ.

## Scenes (2026-11-20, tenth session; `tools/debug/scenes.py`, `warp.lua`)
- `$2BF6` ("map") is an event id: the loader (6A:`$69E8`) runs it through 6F:`$7977`. Header entry 3 = u16 per sub ->
  object list -> 3-byte entries (event id, script pointer); `scenes.py ISO AREA` lists the ids per sub (subs below 0x10
  read junk). Script opcodes: table at 6F:`$6653` (op*2), op 0x03 = in-area warp (sub, map, entrance), op 0x71 = full warp.
- A sub's own message group has the same number as the sub (sub 0x11 = house = group 0x11; sub 0x23 opened group 35).
- Area 0x10: sub 0x20 = first village (map 2, entrance 5 = at the gate; place card "Village"). Its interiors are subs
  0x14-0x27 (even subs: map 2 / entrance 5, odd: map 3 / entrance 6). Loaded from the preload state they draw with the
  wrong tiles; redirect a load made from the village instead: from `town.mss`, `--route '10:down*150'` (walks out of the
  gate) + `warp.lua --var SUB=0x19 --var MAP=3 --var ENT=6`, about 700 frames. Sub 0x19 = shop (group 25, the
  shopkeeper on the tatami), sub 0x1C = inn (group 28), sub 0x23 = a house (NPC talks: verified).
- Player position: X = `$2085`, Y = `$2087` (4-px units). `tools/debug/goto.lua` walks to waypoints by these values
  (`PATH='x,y;x,y'`, `FACE`, `TALKS` I presses, `START` frame: after a map load the player moves only ~300 frames later).
  Shopkeeper of sub 0x19: from (12,18) to (18,18), face up. `show.py --regen` saves `town.mss` (gate) and `shop.mss`
  (inside the buy menu).
- Shop main-program text (title 道具屋, 買う / 売る / やめる, お品書 / 値段 / 両, buy / sell prompts, はい / いいえ) is in
  English since a60d371 (script/main.json). Not checked since: 持ち金 and the item description line.

## Save screens (traced 2026-11-21, fourteenth session; `tools/lua/rwatch.lua`)
- Bank 0x74 (iso 0x57000, mapped at $6000) holds the Continue menu / BRAM code only before the game starts: in game
  the area event block is loaded over banks 0x74+ (reads of "$9140" in town are event scripts, not the strings here).
- `rwatch.lua --var RBANK=0x74 --var RLO=0x113B --var RHI=0x118F` (offsets inside the bank, every window watched)
  found the slot-line builder: 74:$6F70. `$5404` starts a buffer at $E66E and appends the inline-pointer string
  (`JSR $5404 / BIT ptr`), `$540C` appends a string, `$4921` + inline pointer appends a number, `$50DE` prints it.
  Order: prefix $6FE1 `{14}[80]{06}` (pointer at 74:$6F7A), level, `{04}段{06}/` $6FE5 (ptr $6F86), virtue,
  `{04}徳{06}/` $6FEB (ptr $6F92), province ($6FF5: LDA #$3B STA $95 LDA #$71 STA $96 = base $713B, index from
  $7012 = area $2BF4 >> 3 via the table at $7190, 0x87 -> 0x0F, 0x96 -> 0x0E; $4665 = skip-N-NULs, $5434 append),
  `の国` $700D (ptr $700A), `{06}/` $6FF2 (ptr $6F9B), time ($702B). Header `{05}AREA   TIME` at $6FD3 is ASCII already.
- Province list 0x5813B ($713B): 17 x (2 kanji + NUL): 火多 尾張 伊勢 紀伊 　京 近江 越前 越中 越後 因幡 出雲 石見 丹波
  浪華 吉備 安芸 長門. Script spellings: Hida Owari Ise Kii Kyoto Omi Echizen Etchu Echigo Inaba Izumo Iwami Tanba
  Naniwa Kibi Aki Nagato. Free: 194 zero bytes at 0x58F3E ($7F3E-$7FFF, end of bank 74); 256 zeros at 0x5835A
  (probably a buffer: don't use).
- 57720 (末初期化してゲームを始めます / １．火多〜尾張 ...) is the debug chapter select (left Japanese on purpose).

## Map tilesets (traced 2026-11-21, thirteenth session; `tools/gfxscan.py`, `tools/lua/gfxwho.lua`; survey in graphics.md)
- Every map graphics block goes through 69:`$46C4` (LZ init, A:X = source) and the writer loop 69:`$4700`-`$470D`
  (`lz.unpack_rings`, header u16 word count, bit 15 = ring B). Two sources:
- Event block descriptor (6A:`$6201` walks it, pointer in `$53`): `[u16 0][u16 e1][u16 e2 or 0][0]`, entries are signed
  16-bit offsets from the descriptor (wrap: a sub shares another sub's block by pointing back), one entry is 8 = its own
  block right after it. Area 0x10: village 0x18D0E -> 0x18D16 (VRAM $1000, 0xC00 words) + 0x19EDA ($1C00); shop
  0x1CE77 -> -0x4161 (= 0x18D16) + 0x1CE7F. Offsets here are block offsets (block = sector area*128+2; bank 0x74 + n).
- ADPCM image (sector area*128+98, 64K; 6A:`$61B8`, A < 6 selects): 69:`$498C` A=2 follows u16@0 -> u16@there = table
  `t`; tileset v = u16 at t+2+2v (area 0x10: t=0x3A70, 0x3A76 = overworld, 0x6B92). Read through the 256-byte AD_READ
  buffer at `$2AE3` (source shows as `$2AE5`).
- Tiles are 16x16 metatiles stored TL TR / BL BR = n, n+1, n+16, n+17: render with 16 tiles a row to read them.
- The first stream at the ADPCM image head (`f00f` ...) is not tiles (decodes to noise as 4bpp).

## Battle group 11 (traced 2026-11-20, tenth session; `tools/lua/msgwho.lua` logs every message open and `$752A` print)
- 6B:`$6D9D` (far-called from 69:`$5616`) opens group 11 message A into the buffer `$E66E` through the normal pre-expander
  (dictionary codes work); 69:`$5601` prints it at the cursor (`$50E6`), 69:`$560A` the same with `$3211` (`$50E7`).
- The only callers are in bank 70 with fixed numbers: 126 `が現れた` (70:`$61DC`, a battle-script op printed straight
  after the enemy name), 127/128/130 target prompts after the actor's name, 129, and 118-125 (tactic names, table at
  70:`$757E`). Messages 0-117 (`$0` phrases) and 131-149 have no caller found (absolute JSR, BSR and far-call scans).
- Fragments follow a name with no space between, so their English starts with " " or ","; insert.py keeps a leading space.
- Battle states: the command cursor is wherever the walk left it; `tools/lua/home.lua` homes it on Fight, then `--mash 30` fights.

## Enemy records (traced 2026-11-20, eighth session; `extract.enemies`, `insert.enemies`)
- Enemy names and their status / flee / attack lines are plain SJIS in each area's ADPCM image (iso `area*0x40000 + 0x31000`),
  99 areas below the mirror (1,184 records, 275 names, 277 lines). Image header: u16 end of the record section, u16 n,
  n u16 enemy block offsets, 0, then 4 u16 section offsets; the last one is also enemy 0's record pointer (= section start).
  Enemy block + 6 = u16 ADPCM address of its record.
- Record: 21 bytes of stats, name NUL, 1 byte (`$F670`), entries (kind, param, message NUL) up to a 00, then 2 bytes
  (`$F68A/B`) that are often the next record's first two bytes. 71:`$7F9E` reads 256 bytes from the record's ADPCM
  address into `$2AE3` (AD_READ), name at `$2AF8`; 71:`$7FA6` walks it by NULs and keeps each message's offset
  (`$F671,X`); 71:`$7D80` sets the pointer `$F659` that 71:`$752A` copies to `$E66E` (`$0`-`$3` -> `1D n+1`,
  `$n` -> `0D`, everything else raw, no dictionary). So records can move anywhere in the image if the pointer follows.
- Data after the section (a u16 table at `end`) is left in place. Room: section + the FF run before the battle stream;
  in 38 tight areas (6 free bytes there) records spill into zero / FF padding that ends a blob on a 0x800 boundary
  (64-byte margin; assumed unread, guess).

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
