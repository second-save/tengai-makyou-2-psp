# Status

Goal: English patch for Tengai Makyou II: Manji Maru, PSP PC Engine Archives release (NPJJ30036).
User rulings: shorter names (avoid overlap/overflow), keep **Jipang** (world), **Virtue** (XP), **Ryo** (money), build a VWF.
Translation source: the user's own DS translation, `~/develop/tengai-makyou-2-ds/tengai-makyou-2-ds/translation/tengai2_script.translated.json`
(11,661 lines: `id` like `wa1/vaa1.scs#0`, `jp`, `jp_clean`, `en`), plus `glossary.json`, `native_catalog.json`, `combat_text.json` there.

Phase: 1 (recon) nearly done, 2 (debug tool) half done: dialogue viewer, battle viewer and warp work, shop / town scenes do not yet,
4 (extract) done for the message modules, 5 (engine spike) VWF working, DS English inserted for 189 blocks (first build).

## Release route: the PC Engine translation ported (2026-11-22, fifteenth session)
- User ruling: ship the PC Engine project's v0.9 translation (`~/develop/tengai-makyou-2-pce-cd`) on the PSP; this repo's
  own pipeline (DS text) is not what gets released.
- CONTENT.DAT's data track = the PC Engine track 02 minus its 0xE6-sector pregap, with 108 sectors of Hudson edits:
  one far call (`JSR $4921 / BIT $6DE8`) inserted in engine banks 6B (+0656), 6E (+0337), 74 (+09CF, then +0A25: +7),
  code after it moved; event code changed in areas 35 / 110 / 124 (the PC Engine ids 23 / 6E / 7C); area 35 lost the two
  first lines of group 17; mirror copies at sector 65536+.
- Build there: `tools/tm2_text.py build work/en_build --ascii --psp work/content/HCD1022_02.iso` -> `build/tm2_psp.iso`
  (`tools/tm2_psp.py`: engine patched on the PC Engine engine, then moved through the shift map; `check` = the map agrees
  with Hudson's own relocation of all 153 string pointers). Pack here:
  `tools/content.py pack work/content rom/NPJJ30036/PSP-KEY.EDAT build/pce-port/CONTENT.DAT .../build/tm2_psp.iso`.
- Mesen QA (PSP track vs PC Engine build, same script): file screens, Info, first dialogue, shop route and a battle are
  pixel-identical. Not tested on a PSP or in PPSSPP yet.

## Done (2026-11-19) - details in docs/re/notes.md
- No English patch exists for the PC Engine game (web search). Related repos on this machine: `~/develop/tengai-makyou-2-pce-cd`
  (June notes; its decompressor theory is wrong, ignore it; `tools/dis6280.py` copied from there) and
  `~/develop/tengai-makyou-collection-psp` (another session, same game inside the Collection: share findings).
- Container: `tools/content.py unpack|pack|test` (CONTENT.DAT XOR + archive + zlib-chunked data track). Identity test passes.
- Emulator: `tools/mkcue.py` + `tools/pce.py` boot the data track headless in MesenCE 2.2.1 (`tools/mesen`, firmware = first 256K of
  SYSCARD3P.PCE). States in `work/states/` (`preload.mss`, `house.mss`). Route to the first dialogue is in notes.md.
- Compression: `tools/lz.py` (unpack + greedy pack, self-check passes). Verified on the first dialogue.
- Message system understood: event block -> group table -> dictionary + LZ streams of NUL-terminated messages; control codes of
  the pre-expansion stage; DS script lines match PC Engine messages one to one (same text, same control codes).
- `tools/extract.py ISO OUT.json`: 189 text modules, 10,478 unique message pages -> `work/script/blocks.json` (messages as hex).

## Character table and DS matching (2026-11-19, second session)
- `tools/align.py BLOCKS.json DS.json work/script/table.json work/script/match.json [--why KEY]` learns the table by aligning with
  the DS script and writes the match (PC Engine `sector/group/message.page` -> DS `id@segment`). Table is complete except byte 0x20:
  0x21-0x60 and 0x7A-0x7F = frequent kanji/signs (0x30-0x39 = full-width digits), 0x61-0x79 = voiced kana (が..ぽ),
  0xA1-0xDF = kana; `0E`/`0F` switch katakana/hiragana for the kana ranges only. Kana gaps were filled by the regular
  order (inferred, not yet seen drawn). Not yet written as a `tbl.py` table, no roundtrip test yet.
- One PC Engine message = several DS lines: the DS script has one line per page (pages end at the wait code `12`), and a DS
  line can hold several messages separated by `{0000}`. `＠` is DS-only padding; DS timing arguments differ.
  `1B` takes one raw argument byte; `1A` = name placeholder; `16 05 ... 04 ... 08` = place-name cards.
- Dictionary codes (`1F nn`) work at byte level: a word can supply the second byte of a kanji. Expand before parsing.
- Extractor fixes this session (all were silently losing text): header and group pointers are plain 16-bit block offsets
  (no bank masking); the three JMP targets in the module signature vary (203 modules, 189 with text = those carrying the
  106-word dictionary); the group table ends at a 00..0F byte ramp, at FF padding or at the dictionary; every stream is cut
  at the first message that is not valid text after dictionary expansion.
- Coverage: 13,833 of 14,413 DS segments are found on the PC Engine side (96%). PC Engine side: 8,480 of 10,478 unique
  pages have a DS line; 674 area pages and 1,319 system pages (groups 2-13: item names, battle and menu messages) do not.

- `tools/codec.py` (+ `tools/table.json`, a copy of the learned table): bytes <-> text, `codec.py test BLOCKS.json` roundtrips
  all 8,497 distinct messages byte-exact.
- `tools/script.py BLOCKS MATCH DS_SCRIPT script/messages.json DS_CATALOGS...` builds the working script: 8,375 messages,
  10,869 pages, 9,536 with DS English (script + `native_catalog.json` + `combat_text.json` by exact text). 1,272 messages
  still need English: group 5/6/7/9 = 450 hiragana readings of item / technique names (check whether they are ever shown),
  group 11 = 216 battle technique lines, group 10 = 33, area groups = 566.
- In battle text (group 11) `24 3x` looks like a name placeholder ("$0", "$1"), not 子 + digit (guess, from the text).

## Insert pipeline (2026-11-19, fourth session) - first dialogue verified from a cold boot
- `tools/insert.py ORIG SYSCARD BUILT BLOCKS script/messages.json [--marker]` (run after `build.py --all-ascii`, about a minute):
  all 189 blocks rebuilt and read back by the extractor, 0 blocks without room; `romdiff.py --writes` passes.
  Cold boot + walk to the mother (`work/qa/ins1`): English draws, dictionary codes expand, wrap is right. An 8-line test
  message (`work/qa/long1`) pages 3 lines at a time: after `12 0D` on a full window the window clears and restarts at the top.
  pce.py `--mash` runs for the whole route, so it also skips the waits: shoot early or drop it once in control.
- Room: English is about 45% larger after LZ. Fixes: streams also go into FF runs (64+ bytes) below block offset 0x10000;
  dictionary (group 1) replaced by 128 English strings coded as one byte 0x80-0xFF (hook `dict` in `src/vwf.s`, bank 69
  $5FE6, called from 6F:$7EA8; saves about 21%); reading groups 5/6/7/9 share the stream of name groups 2/3/4/8.
- A message without English keeps its control codes and shows `?` per glyph.
- `1B` (number) has no argument byte (`1B 8C C2` = number + 個); extract.py / align.py still skip one byte after it.
- Extractor fix: empty groups parked on the group table were decoded as junk messages (script regenerated: 8,330 messages).
- `build/tm2_02.iso.insert.log`: 1,325 lines wider than 216 px (wrap is one width for every window: width gate not done),
  119 pages where the English lost a choice marker (`01`), 9 other placeholder mismatches.
- Unverified guesses: FF runs are free at run time (the start block uses none past its table: test one that does);
  streams end where the extractor cut them; spaces do not erase (the VWF composes by OR).

## Debug tools (2026-11-20, fifth session) - details in notes.md "Map loads and warping"
- `python3 tools/debug/show.py --out DIR ITEM...` shows any message in the dialogue window, about 3 s each, 8 in parallel,
  one shot per page (`DIR/<item>/pNN.png`), exit 1 if a message does not run to its end. ITEM = `sector/group/message`
  (read back from the built disc) or `text:...`. It talks to the mother from `work/states-en/house.mss` and
  `tools/debug/msg.lua` swaps the stream in RAM. Verified on dialogue, item names and raw text.
- `python3 tools/debug/show.py --regen` (about 6 minutes; probes the frame of the house load first) rebuilds `preload.mss`, `house.mss` and `battle.mss` in
  `work/states-en/` from a cold boot and checks that a message shows. Run it after every rebuild.
- `tools/debug/warp.lua` (`--var AREA= SUB= MAP=`) redirects the next map load: verified for the overworld of the start
  area (`SUB=0x12`, field menu opens, random battles happen). `tools/debug/battle.lua` walks until a battle starts.
  No scene list yet: valid sub / entrance values per area are not enumerated, no shop or town reached.
- Width gate, dialogue window: a line up to 219 px stays on one line, 224 px wraps by itself onto the next line.
  `insert.py`'s 216 px and 3 lines per page are confirmed (`work/qa/width`).
- Seen in the battle state on the English build: the prompt, the command names and the enemy name line are still
  Japanese (main program), the hero's default name is stored as kanji and draws as garbage, and the game prints the
  actor's name before a battle line, so battle lines have less room than the window. The battle window wraps by itself.
- `]` and the digits have the game's own glyphs: `]` draws as a kanji-like sign, use `<>` in markers.
- Battle messages with name placeholders (`19 n`) end at once outside a battle: they need the battle window.
- pce.py: parallel runs no longer rewrite Mesen's settings.json (one run read it half-written).

## Battle viewer (2026-11-20, sixth session)
- `python3 tools/debug/show.py --battle --out DIR ITEM...` (ITEM may be `battle/N`) shows any message in the battle window (from `battle.mss`:
  msg.lua homes the command cursor by RAM value, Fight + first target, the attack line is replaced in ADPCM RAM).
  Verified with raw text and module messages. Width gate, battle window: wraps by itself at 28 tiles, 3 lines; the
  name placeholder takes its width out of the first line.

## Enemy records (2026-11-20, eighth session) - details in notes.md "Enemy records"
- Enemy names and their status / flee / attack lines live in each area's ADPCM image (plain SJIS, 99 areas, 1,184 records),
  not in the modules or the battle stream. `extract.enemies` reads them, `script.py` adds them as `enemy/N` (551 strings:
  509 from the DS catalogs, 42 written here in `script/overrides.json`), `insert.py` rewrites every area: 99 of 99 in English.
- Room: DS lines were too long for the 44 tightest areas. Your shorter-names ruling applied: terse overrides for ~55
  lines and 15 names (e.g. "Bone Hound", "Chimi", "$0 charges!"). 38 areas also spill records into sector padding
  (zeros / FF up to a 0x800 boundary, 64-byte margin): assumed unread, not proven (`shortcut:` in insert.py).
- Verified: a fresh battle from the old `battle.mss` with area 0x10's new image loaded by `tools/debug/adpcm.lua` shows
  "Rabid Dog / fled!". Not verified: an area whose records sit in padding (no warp to one with battles yet).
- The garbled top box in battle is the party status (hero's kanji name), the same before this change.
- Padding verified (ninth session): area 0x10's records moved into its zero padding at $9A43 (old section filled with
  junk), loaded with `adpcm.lua`: a fresh random battle reads them ("Stray Dog / fled!") and the overworld redraws
  cleanly after it. Not checked in the 38 real padding areas themselves.
- `show.py --regen` fixed (ninth session): the "flaky intro" was Mesen's backup RAM (`tools/mesen/.../Saves/tm2.sav`,
  shared by every run): a save written by one run changed the next cold boot's new-game path. `pce.py` now deletes it
  before every cold-boot run; regen is deterministic again (house load at f=14453) and accepts a black preload frame.

## Main-program strings (2026-11-20, tenth session) - details in notes.md "Main-program strings"
- `tools/mainstr.py ISO OUT.json` lists candidate UI strings (heuristic; `work/script/main_strings.json`);
  `script/main.json` holds the curated ones (at, original hex, jp template, en template, note, pad); `mainstr.py insert`
  writes them in place (both copies), refuses one that grew or whose original is not followed by a NUL.
  Templates: `{XX}` code, `[XX]` raw argument byte, `{00}` a NUL inside a list. Lists read by skipping NULs pad with `20`.
- `tools/make.sh` = build + insert + mainstr insert + romdiff + cue; then `show.py --regen` (now also town, shop, menu).
- English on screen: battle menu (Fight Sword Run / Scroll Guard Stats / Items Plans ??), Guard sub-menu, "Go, Manji!!",
  field menu (Status Items / Scrolls Gear / Techs), shop menus, prompts and names, Yes/No, item / scroll / gear action
  menus, give / drop prompts, effect categories ("/Heal"), status bar name ("Manji 体 37"), kind names ("Use which Item").
- Engine changes (build.py): battle menu slot 2 names 6 bytes (70:$7646 loop, table 70:$7FDE); field menu printed from a
  copy in 6E ($665B far call, 6E:$7FB8 routine, string at $7FBF); kind / party name lists moved in 6B (bases at
  $6CF8 $6D10 $6D75 $6D7B $6CDC $6CD3); status bar name room 24 -> 32 px (6B:$61D2); VWF room check 8 px wide, 16 px
  high in windows of 6+ tiles and 8 px in smaller ones (status bar).
- Also English since: status bar labels (glyphs for `_ ^ ]` redrawn as Lv TP HP), status screen (Virtue label moved to
  6B:$6C61, all name-list bases incl. 6B:$6D84/$6D8D), Ryo in the field money window (moved to 6B:$6C55) and shop.
  build.py checks the original bytes under each code patch (an off-by-one pointer patch broke a screen once).
- Left in Japanese: 両 in storage / bank lines, status ailments (2-3 bytes), storage / bank menus,
  save screens (0x576CC-0x58800, not resident), province names 0x58140, the ship commands in battle slot 9.

## Remaining script text (2026-11-21, eleventh session)
- 54 messages written in `script/overrides.json` (`_remaining`): Takako's 5 letters (both modules 514 and 4994), the
  4994 battle / fortune-teller lines, ailment short names (same as main.json), 7 item names. Letters checked on screen
  (`work/qa/letters`); their "wider than 216 px" log lines are the trailing space at a wrap, not overflow.
- Left without English on purpose: hiragana reading groups 5/6/7/9 (share the English name streams), group 11 `$0`
  phrases 0-117 / 131-149 (no caller), debug menus (sound / video test, `chNNN`, YAV, ABORT), ~50 garbled stream-tail
  fragments (`立立に`, `なない`: extractor cut points, open problem 2), and the kana name-entry grid 4226/17/0
  (needs engine work: the cursor picks kana from a code table, the text alone can't change it).

- Main program, same session: 28 more `script/main.json` entries: title Continue menu (Saves / Load Copy Erase Info,
  slot states, prompts; verified from a cold boot: `1200:run*10;1500:run*10;2000:right*10;2150:i*10`, then `2700:i*10`
  = Load), backup memory and file-delete messages (not seen on screen), ship commands (4-byte table 70:$7711:
  Guns Atk Fire Torp Heat), stat-change lines, " uncursed!", "Enemy crushed!", minigame "Which wins?".
  The same BRAM strings also sit LZ-compressed in areas at 0x3510000+ (left alone; the screen uses the plain copy).
  Still Japanese in the main program: province names 0x58140 (4 bytes each: need the list base to relocate),
  summon names 0x50AC1 (名無し シロ 式神 三角), debug menus (chapter select 0x5771D, battle test 0x4F213 / 0x510C6).

## Save screens (2026-11-21, fourteenth session) - details in notes.md "Save screens"
- A save to test with: `work/states-en/inn.sav` (backup RAM, Stay+Save at the first village inn); `pce.py --sav F`
  starts with it (every run now leaves `OUT/bram.sav`). Continue > Info from a cold boot:
  `--sav work/states-en/inn.sav --route "1200:run*10;1500:run*10;2000:right*10;2150:i*10;2500:right*8;2600:right*8;2700:right*8;2850:i*8;3100:i*8"`
  (slot line at f2900, Info at f3300). Inn: `work/states-en/inn.mss` = innkeeper menu open (old man by the hearth;
  from town.mss: route `10:down*150`, warp.lua SUB=0x1C MAP=3 ENT=6, goto PATH `12,26;22,26;22,18;16,18` FACE up).
- Info screen garbage fixed (fifteenth session): it reads item names from a Japanese copy of system groups 1-11 in
  the boot image (iso 0x59000, bank 75), and the dictionary hook took its SJIS bytes for word codes. insert.py now
  rebuilds that copy too (`extract.SYSTEXT`, block 178). Gear / Item now read "Takemitsu  Rags" / "Soba Dango".
- Slot line still Japanese: "3段/ 20徳/火多の国/ 0:01" (Lv, Virtue, province, play time). Plan in notes.md: new strings
  and an English province list in the zero tail of bank 74 ($7F3E-$7FFF), inline pointers re-aimed (build.py).

## Ending staff roll (2026-11-21, twelfth session) - details in notes.md "Programs and the ending staff roll"
- User ruling: credits in English (roll + opening card), title logo stays kanji (docs/decisions.md).
- Graphics survey of the cold boot (intro, title): only the opening card 制作・総指揮 工藤裕司 (graphics) and the
  kanji logo (kept) are Japanese; the ending roll was the only other credit text.
- `tools/debug/prog.lua --var PROG=0x9E` runs the ending from a cold boot. `script/roll.json` (264 records, English
  from the DS `staff_roll.json`, names in Western order, 43 written here: different producer Yuji Kudo, PC Engine
  name variants, the company list) inserted by `tools/roll.py` (in make.sh); `src/roll.s` draws two ASCII
  characters per 16-px cell. Verified from a cold boot through the whole roll (`work/qa/end4`, `end5`).
- Readings to review: Atsushi Hayashida (林田淳; DS had 敦), Yoshihiko Inamoto (義彦; DS 亀彦), T. Hamada (濱田敏徳),
  Shin Sasaki. DS abbreviations kept where the full word does not fit 32 columns (Music Superv., Sound Dir., Anim.
  Director, initials).

## Open problems
7. Battle text (done 2026-11-20, seventh session): the 235-line battle stream is in the script (`battle/N`, 225 of
   230 distinct lines have English from `combat_text.json`) and inserted in all 370 copies. It packs to 0xC2E bytes
   with `lz.pack_best` and starts early in the FF padding before it (71:`$7502` patched). Room is tight: now 51 of the
   56 free bytes in the 92 tightest copies (the 5K before it is shared battle data in two versions, not free). Longer
   battle English needs room first: drop unused lines (`battle/204` "Coming soon" is likely debug) or tighten wording.
   All 230 distinct lines have English: 6 come from `script/overrides.json` (hex -> English, applied last by script.py,
   written from the nearest DS combat lines). Left: `battle/91` and `battle/155` logged wider than 216 px;
   verified in a real fight from a cold-boot state (`狂犬 takes 4 damage!`).
   Still Japanese in battle: the prompt and command menu (main program), the hero's default name. Enemy names and
   lines: done (see "Enemy records").
1. Unmatched text. DS side: `end0`-`end3`, `v172`, `xk8` not found at all (ending / cutscene text, probably stored outside
   the message modules), `xj4` 50/105 (was 71 before the 106-word filter: one of the 14 dropped modules may hold text),
   and 5-40 lines short in about 25 area directories (likely small wording differences: the match is exact).
   PC Engine side: the 1,319 system pages should be matched against the DS `native_catalog.json` / `combat_text.json`.
2. Stream ends are inferred (cut at the first invalid message). Confirm against the message counts the scripts actually
   use before reinserting.
3. Main-program text: in progress (see "Main-program strings").
8. Long dialogue messages (fixed 2026-11-20): the pre-expansion buffer at $E66E holds 256 bytes and the game wrote
   "長い!" (too long) when it filled; ~340 English messages pass it. build.py now draws and empties the buffer at
   every page end (6F:$7FD3 store tail -> 69:$5FE6, MPR4-5 saved across the key wait). Verified in game on the shop
   tutorial (2050/25/4, 5 pages; sub 0x19, goto `12,18;22,18` face right, Yes). Limit: one page over 256 bytes would
   still overflow, now unguarded (the "長い!" guard is gone); pages are 3 lines, far below that.

## Next steps
1. PSP-side test (blocker for release): boot `build/CONTENT.DAT` (or the original + `dist/tm2-en.xdelta`) in PPSSPP
   or on a PSP; the file grew by 978,432 bytes. PPSSPP is installed: `/Applications/PPSSPPSDL.app` (user, 2026-11-21).
2. Graphics text: start menu panel and its 起 / 転 buttons done (eleventh session, `tools/panel.py`, NEW / LOAD).
   Opening card done (twelfth session, `tools/card.py`: "Executive Producer / Yuji Kudo", in make.sh).
   In-game survey done (thirteenth session, `docs/re/graphics.md`): shop signboards 武 雑 宿 領 道 薬 (16
   town tilesets) and the money-changer board 両売替… (4 interior tilesets) stay kanji (ruling). The "卍丸さん江" letter picture
   (area 0x1C) stays as art (ruling, decisions.md). Not covered: game over, battle graphics, cutscene pictures beyond the tour.
   Tools: `tools/gfxscan.py` (decodes every map tileset), `tools/debug/tour.py` (warp + shoot per area/sub),
   `tools/lua/gfxwho.lua`, `tools/tilefind.py`. Redraw path: a `gfxscan`-style insert (re-pack with `lz.pack_rings`,
   same block size or relocation) for each of the 16 tilesets.
3. Ending: staff roll done; the ending scenes before it (f~200-4000) show no text. DS `end0`-`end3` text: still
   to confirm voice-only (the ending program has no message stream).
4. Main-program leftovers (save screens, fourteenth session; see "Save screens" below): **the Continue > Info
   screen's garbage is fixed (fifteenth session)**; next the
   slot line (Lv / Virtue / province / time). Also: 毒 (2 bytes), summon names 0x50AC1, 両 in storage / bank lines,
   storage menus not seen on screen yet, the width gate for the other windows. (Ship commands and the Continue menu,
   file manager and BRAM messages were already done.)
5. Font polish (W/M touch neighbours), text speed. Review the ~150 messages translated in the tenth session
   (`script/overrides.json`, page lists) and the 169 near-miss pages (`ds` = "near:...").

Build: `tools/make.sh` (build, insert, main strings, write check, cue), then `python3 tools/debug/show.py --regen`. Cold boot to the house: 16000 frames,
route `1200:run*10;1500:run*10;1800:run*10;2100:i*10;2400:i*10 --mash 40` (about 50 s).

## Housekeeping
- Commits use the repo-local identity `second-save <second-save@users.noreply.github.com>` (user ruling 2026-11-19: work is published under the second-save org). No remote yet; ask before creating one.
- Skill path helper `tools/skill.py` points at the plugin path, which does not exist here; the skill is at
  `~/.claude/skills/translate-retro-game` (set `TRANSLATE_SKILL`).
- Step 0 leftovers not done: instructions file (AGENTS.md), pre-commit hook, guard-hook canary.
