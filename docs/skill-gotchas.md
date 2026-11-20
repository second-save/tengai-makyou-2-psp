# Skill gotchas (one line each: reference file it belongs in, then the fact)

- emulator-qa.md: Mesen `--testRunner` does not exit on a Lua syntax error: it runs the game without the script until `--timeout`. A run that produces no log and no shots for minutes = check the script parses first.
- emulator-qa.md: parallel headless Mesen runs must not each rewrite `settings.json`; one run read it half-written and crashed. Write it only when it changes, through a temp file and a rename.
- emulator-qa.md: a savestate carries the program it was made with. A state made before the last rebuild showed the old text path (kana instead of English) and looked like an insert bug.
- emulator-qa.md: `sheet.py DIR` only picks up `f<frame>.png` names; copies named otherwise are ignored.
- emulator-qa.md: a shot taken 3 frames after the game reaches its wait-for-button code can miss the last glyphs; 10 frames was enough here.
- emulator-qa.md: macOS `xargs -I{}` refuses a long command line ("command line cannot be assembled, too long"); use a shell loop with `&` and `wait`.
- emulator-qa.md: a random battle reached by a scripted walk is not a fixed scene: the encounter and the command cursor differ between runs, so presses that work in one state do nothing in the next.
- platform-psp.md (PC Engine CD): ADPCM RAM is used as a 64K data cache (AD_TRANS in, AD_READ out): text read from it never shows up in the CPU address space, so a CPU-side poke of the 'source address' does nothing. Dump `pceAdpcmRam` in Mesen.
- emulator-qa.md: a menu cursor that wraps cannot be homed with presses from an unknown position; find its RAM variable (dump after each of 4-5 known moves and match the sequence) and set it.
- emulator-qa.md: a savestate taken at a fixed frame of a boot route drifts when text changes the intro's length (English build: the house load moved before frame 14300 and a map-load hook in the state never fired). Probe the event's frame in a first run, then save the state a little before it.
- emulator-qa.md: `build && insert 2>&1 | tail -1 && next` carries on after a failed insert (the pipe returns tail's status) and regenerated states from a half-built disc. Use `set -o pipefail`.
