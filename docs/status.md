# Status

Goal: English patch for Tengai Makyou II: Manji Maru, PSP PC Engine Archives release (NPJJ30036).
User rulings: shorter names (avoid overlap/overflow), keep **Jipang** (world), **Virtue** (XP), **Ryo** (money), build a VWF.
Translation source: the user's own DS translation, `~/develop/tengai-makyou-2-ds/tengai-makyou-2-ds/translation/tengai2_script.translated.json`
(11,661 lines: `id` like `wa1/vaa1.scs#0`, `jp`, `jp_clean`, `en`), plus `glossary.json`, `native_catalog.json`, `combat_text.json` there.

Phase: 1 (recon) nearly done, 2 (debug tool) half done: dialogue viewer, battle viewer and warp work, shop / town scenes do not yet,
4 (extract) done for the message modules, 5 (engine spike) VWF working, DS English inserted for 189 blocks (first build).

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
1. Battle group 11: done for the messages the code uses (2026-11-20, tenth session; notes.md "Battle group 11").
   Verified in game: "Rabid Dog appeared!" and "卍体, which foe?". Left: messages 0-117 and 131-149 have no caller
   in the main program (guess: unused leftovers, the battle stream holds their equivalents); if one ever shows as
   `?????`, run `tools/lua/msgwho.lua` to find it.
2. Debug tool: village (`town.mss`) and the shop's buy menu (`shop.mss`) come out of `--regen` (notes.md "Scenes";
   `goto.lua` walks by RAM position). Left: a warp to one of the 38 areas whose enemy records sit in padding (e.g. area
   18, record at $9321; `scenes.py ISO 12` lists its subs and events), the width gate for menus and shops.
3. Main-program strings: finish the list under "Main-program strings" (left in Japanese), then the width gate.
4. Find the ending / cutscene text. Messages without English: script.py now fills pages from near-miss DS lines
   (ratio >= 0.9, `ds` = "near:<id> <ratio>", 169 pages) and `script/overrides.json` takes a list of page English;
   ~150 area messages translated here (tenth session; `work/script/todo.json` was the list). 8,200 of 9,111
   messages fully English. Left on purpose: debug menus (514/16, 642/16, 770/16, 898/16, 5890/16 "chNNN", 4226/17 kana
   grid), garbled fragments in boss modules (25730+/16: stream junk past the real messages, guess), blank erasers,
   and system groups 5/6/7/9 (hiragana readings, probably never shown) and 11 (no caller).
5. Font polish (narrower W/M or a redrawn font in SYSCARD3P.PCE bank 1), text speed.
6. Rebuild CONTENT.DAT, QA, release as a patch on CONTENT.DAT.

Build: `tools/make.sh` (build, insert, main strings, write check, cue), then `python3 tools/debug/show.py --regen`. Cold boot to the house: 16000 frames,
route `1200:run*10;1500:run*10;1800:run*10;2100:i*10;2400:i*10 --mash 40` (about 50 s).

## Housekeeping
- Commits use the repo-local identity `second-save <second-save@users.noreply.github.com>` (user ruling 2026-11-19: work is published under the second-save org). No remote yet; ask before creating one.
- Skill path helper `tools/skill.py` points at the plugin path, which does not exist here; the skill is at
  `~/.claude/skills/translate-retro-game` (set `TRANSLATE_SKILL`).
- Step 0 leftovers not done: instructions file (AGENTS.md), pre-commit hook, guard-hook canary.
