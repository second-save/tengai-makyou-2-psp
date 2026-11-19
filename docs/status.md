# Status

Goal: English patch for Tengai Makyou II: Manji Maru, PSP PC Engine Archives release (NPJJ30036).
User rulings: shorter names (avoid overlap/overflow), keep **Jipang** (world), **Virtue** (XP), **Ryo** (money), build a VWF.
Translation source: the user's own DS translation, `~/develop/tengai-makyou-2-ds/tengai-makyou-2-ds/translation/tengai2_script.translated.json`
(11,661 lines: `id` like `wa1/vaa1.scs#0`, `jp`, `jp_clean`, `en`), plus `glossary.json`, `native_catalog.json`, `combat_text.json` there.

Phase: 1 (recon) nearly done, 2 (debug tool) half done: dialogue viewer and warp work, battle / shop scenes do not yet,
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
- `python3 tools/debug/show.py --regen` (4 minutes) rebuilds `preload.mss`, `house.mss` and `battle.mss` in
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

## Open problems
7. Battle window viewer: `show.py --state work/states-en/battle.mss --route ...` replaced the first battle message in one
   encounter (group 11 message 127 opened on the first press) but opens no message in the encounter the current
   `battle.mss` holds (the command cursor starts on the second row; homing it with up/left did not help). Needs a fixed
   encounter (find the encounter roll) or a hook on the battle's own message call instead of button presses.
1. Unmatched text. DS side: `end0`-`end3`, `v172`, `xk8` not found at all (ending / cutscene text, probably stored outside
   the message modules), `xj4` 50/105 (was 71 before the 106-word filter: one of the 14 dropped modules may hold text),
   and 5-40 lines short in about 25 area directories (likely small wording differences: the match is exact).
   PC Engine side: the 1,319 system pages should be matched against the DS `native_catalog.json` / `combat_text.json`.
2. Stream ends are inferred (cut at the first invalid message). Confirm against the message counts the scripts actually
   use before reinserting.
3. Main-program text (menus, shops, battle; plain SJIS + the mixed encoding) at iso 0x41000-0x62800 is not extracted yet.
4. VWF: done as an engine spike (`src/vwf.s`, `tools/build.py`, notes.md "VWF"), using the System Card 8x8 font.
   Open: W and M touch their neighbours (8-px glyphs), text sits at the top of the 16-px line, text speed is still one
   glyph per 4 frames, `--all-ascii` works (plain ASCII, no prefix), marker build and width gate for the other windows (battle, menus, shops) not done.
5. Mirror copy of the start of the track at iso 0x8000000: which copy the PSP emulator reads is unknown; patch both.
6. The PSP side is untested: no PPSSPP on this Mac (headless QA fork is Windows-only). QA so far = Mesen with the extracted track.
   The rebuilt CONTENT.DAT must be booted in PPSSPP or on hardware before release.

## Next steps
1. Debug tool, rest of it: battle window viewer (open problem 7), a shop and a town (enumerate sub / entrance values per
   area: the warp opcodes are 6F:`$7839` and 6F:`$6784`, their arguments sit in the area scripts), then the width gate
   for the battle, menu and shop windows. The dialogue window is done; the marker build is not needed for it (`show.py`
   shows a message by id).
2. Extract main-program strings (iso 0x41000-0x62800) into the script.
3. Find the ending / cutscene text; translate the 1,272 messages without English (near-miss matching against the DS
   script first: many differ by a few characters only).
4. Font polish (narrower W/M or a redrawn font in SYSCARD3P.PCE bank 1), text speed.
5. Rebuild CONTENT.DAT, QA, release as a patch on CONTENT.DAT.

Build: `python3 tools/build.py work/content/HCD1022_02.iso work/content/files/SYSCARD3P.PCE build/tm2_02.iso`, check with
`python3 tools/romdiff.py work/content/HCD1022_02.iso build/tm2_02.iso --writes build/tm2_02.iso.writes`, cue with
`python3 tools/mkcue.py work/content/files/HCD1022.hcd build/tm2_02.iso work/cd-en`. Cold boot to the house: 16000 frames,
route `1200:run*10;1500:run*10;1800:run*10;2100:i*10;2400:i*10 --mash 40` (about 50 s).

## Housekeeping
- Commits use the repo-local identity `second-save <second-save@users.noreply.github.com>` (user ruling 2026-11-19: work is published under the second-save org). No remote yet; ask before creating one.
- Skill path helper `tools/skill.py` points at the plugin path, which does not exist here; the skill is at
  `~/.claude/skills/translate-retro-game` (set `TRANSLATE_SKILL`).
- Step 0 leftovers not done: instructions file (AGENTS.md), pre-commit hook, guard-hook canary.
