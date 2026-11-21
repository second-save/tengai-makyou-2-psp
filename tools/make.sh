#!/bin/sh
# Full English build: engine + script + main-program strings, write check, cue. Then run `python3 tools/debug/show.py --regen`.
set -e
cd "$(dirname "$0")/.."
O=work/content/HCD1022_02.iso; SC=work/content/files/SYSCARD3P.PCE; B=build/tm2_02.iso
python3 tools/build.py $O $SC $B --all-ascii
python3 -X utf8 tools/insert.py $O $SC $B work/script/blocks.json script/messages.json | tail -3
python3 -X utf8 tools/mainstr.py insert $B script/main.json
python3 -X utf8 tools/roll.py insert $B script/roll.json
# start menu panel; needs Pillow (python3.12 here: the default python3 has none)
python3.12 tools/panel.py make $O $SC build/panel.bin && python3.12 tools/panel.py insert $B build/panel.bin
python3.12 tools/card.py make $O $SC build/card && python3.12 tools/card.py insert $B build/card
python3 tools/romdiff.py $O $B --writes $B.writes | tail -2
python3 tools/mkcue.py work/content/files/HCD1022.hcd $B work/cd-en
shasum $B
