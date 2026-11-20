#!/bin/sh
# Full English build: engine + script + main-program strings, write check, cue. Then run `python3 tools/debug/show.py --regen`.
set -e
cd "$(dirname "$0")/.."
O=work/content/HCD1022_02.iso; SC=work/content/files/SYSCARD3P.PCE; B=build/tm2_02.iso
python3 tools/build.py $O $SC $B --all-ascii
python3 -X utf8 tools/insert.py $O $SC $B work/script/blocks.json script/messages.json | tail -3
python3 -X utf8 tools/mainstr.py insert $B script/main.json
python3 tools/romdiff.py $O $B --writes $B.writes | tail -2
python3 tools/mkcue.py work/content/files/HCD1022.hcd $B work/cd-en
shasum $B
