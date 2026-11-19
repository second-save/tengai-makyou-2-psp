# Skill gotchas (one line each: reference file it belongs in, then the fact)

- emulator-qa.md: Mesen `--testRunner` does not exit on a Lua syntax error: it runs the game without the script until `--timeout`. A run that produces no log and no shots for minutes = check the script parses first.
- emulator-qa.md: parallel headless Mesen runs must not each rewrite `settings.json`; one run read it half-written and crashed. Write it only when it changes, through a temp file and a rename.
- emulator-qa.md: a savestate carries the program it was made with. A state made before the last rebuild showed the old text path (kana instead of English) and looked like an insert bug.
- emulator-qa.md: `sheet.py DIR` only picks up `f<frame>.png` names; copies named otherwise are ignored.
- emulator-qa.md: a shot taken 3 frames after the game reaches its wait-for-button code can miss the last glyphs; 10 frames was enough here.
- emulator-qa.md: macOS `xargs -I{}` refuses a long command line ("command line cannot be assembled, too long"); use a shell loop with `&` and `wait`.
- emulator-qa.md: a random battle reached by a scripted walk is not a fixed scene: the encounter and the command cursor differ between runs, so presses that work in one state do nothing in the next.
