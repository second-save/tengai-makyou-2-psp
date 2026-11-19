# Status

Goal: English patch for Tengai Makyou II: Manji Maru, PSP PC Engine Archives release (NPJJ30036).
User rulings: shorter names (avoid overlap/overflow), keep **Jipang** (world), **Virtue** (XP), **Ryo** (money), build a VWF.
Translation source: the user's own DS translation, `~/develop/tengai-makyou-2-ds/tengai-makyou-2-ds/translation/tengai2_script.translated.json`
(11,661 lines: `id` like `wa1/vaa1.scs#0`, `jp`, `jp_clean`, `en`), plus `glossary.json`, `native_catalog.json`, `combat_text.json` there.

Phase: 1 (recon) nearly done, 4 (extract) started. Nothing is translated or inserted yet.

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
- `tools/extract.py ISO OUT.json`: 145 event blocks, 8,918 unique messages (293 KB) -> `work/script/blocks.json` (messages as hex).

## Open problems
1. Character table: bytes 0x20-0x7F and part of 0x80+ are voiced kana / frequent kanji / katakana (only a = が, d = げ known).
   Get it from the drawing stage (consumes the buffer at `($97)`, bank 0x6F around $7FC8 -> $5404) or by aligning with DS text.
   Until then DS matching cannot be measured (kanji-only matching found only ~850 of 8,918).
2. 48 of 145 blocks do not have the standard 106-word dictionary (battle/special modules): header entry 4 may mean something
   else there; `extract.py` output for them is not trusted. 97 blocks are standard.
3. Stream ends: bounded by the next stream / header pointers; the last stream of a block is cut at the first invalid message.
   Confirm against message counts the scripts actually use before reinserting.
4. Main-program text (menus, shops, battle; plain SJIS + the mixed encoding) at iso 0x41000-0x62800 is not extracted yet.
5. Drawing/VWF: text is drawn at a 12-px pitch into BG tiles; the routine is not disassembled yet. VWF = make the advance per
   glyph and add an 8x12 Latin font. Width gate (marker build) not done.
6. Mirror copy of the start of the track at iso 0x8000000: which copy the PSP emulator reads is unknown; patch both.
7. The PSP side is untested: no PPSSPP on this Mac (headless QA fork is Windows-only). QA so far = Mesen with the extracted track.
   The rebuilt CONTENT.DAT must be booted in PPSSPP or on hardware before release.

## Next steps
1. Disassemble the draw stage, dump the full character table, write `tools/table.tbl` + codec (roundtrip test on all messages).
2. Fix `extract.py` for the 48 odd blocks; extract main-program strings; build `script/*.json` keyed by block/group/message.
3. Match to the DS script (exact on normalized Japanese), report coverage, translate the remainder.
4. VWF hook + font, marker build, width gate.
5. Insert (re-pack streams, repoint group tables, both disc copies), rebuild CONTENT.DAT, QA, release as a patch on CONTENT.DAT.

## Housekeeping
- Commits use the repo-local identity `second-save <second-save@users.noreply.github.com>` (user ruling 2026-11-19: work is published under the second-save org). No remote yet; ask before creating one.
- Skill path helper `tools/skill.py` points at the plugin path, which does not exist here; the skill is at
  `~/.claude/skills/translate-retro-game` (set `TRANSLATE_SKILL`).
- Step 0 leftovers not done: instructions file (AGENTS.md), pre-commit hook, guard-hook canary.
