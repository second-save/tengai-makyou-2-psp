# Graphics-text survey (2026-11-21, thirteenth session)

Japanese drawn as tiles, not by the font. Rows marked **todo** need a redraw; "keep" = scenery or a ruling.

| # | Element | Where | Source | Status |
|---|---|---|---|---|
| 1 | Start menu panel + 起 / 転 buttons | title | bank 78 resource (`tools/panel.py`) | done (NEW / LOAD) |
| 2 | Opening card 制作・総指揮 工藤裕司 | intro | intro bank 70 (`tools/card.py`) | done |
| 3 | Title logo (kanji) | title | - | keep (ruling, decisions.md) |
| 4 | Shop signboards 武 雑 宿 領 道 薬 (weapons, general store, inn, lord's mansion, tools, medicine), 16x16 kanji on a dark board | every town map | the town tileset, tiles 0xA0-0xAB / 0xB0-0xBB (metatiles TL TR / BL BR = n, n+1, n+16, n+17); same tiles in 16 tilesets: `04_ev_1DF49` `05_ev_0E795` `18_ev_1D88F` `18_ev_2161A` `20_ev_1496C` `30_ev_1734F` `38_ev_1F0B3` `40_ev_1E5D3` `44_ev_19106` `48_ev_18C73` `60_ad_0AD60` `68_ev_1F2A1` `70_ev_1B680` `70_ev_1DE8B` `71_ev_0F7A9` `80_ev_196A6` (first tile 0x60/0x65 in 18 and 70) | **todo** (seen: first village, area 0x10 sub 0x20, 領 on the lord's mansion) |
| 5 | Money-changer board 両 売 替 … (black on white, 4+ kanji, last one cut by the metatile edge) | town interiors | ADPCM tilesets `18_ad_0A847` `20_ad_0A731` `30_ad_0A409` `40_ad_09AEC` (near the top) | **todo**: confirm the full text on screen first |
| 6 | Letter "卍丸さん江" + sender's signature and seal, a brush drawing ("A bad drawing of a boat...") | cutscene, area 0x1C (warp `AREA=0x1C SUB=0x10 MAP=1`) | full-screen picture, not in a map tileset (source not traced) | **todo**: ask the user (redraw or keep as art; the caption already explains it) |
| 7 | Bonfire characters 大 (and a second one) burning on the mountains | night scene, area 0xBF | picture | keep (scenery, the Daimonji-style fires) |

Not Japanese: overworld roundel tiles (round windows), the battle header and status boxes (font text), place cards
(font text, already English). The hex columns at the left of some warped scenes (FFF8 696F ...) are a debug overlay
the warp triggers, not game text.

## How it was surveyed
- Tour: `tools/debug/tour.py --out DIR [--subs 10] [--map 1] AREA...` warps from `town.mss` to each area/sub and
  shoots it. Sub 0x10 of all 203 areas (`work/qa/gtour`), subs 0x11-0x27 of areas 10 30 3F 5C 7E with MAP 1-3
  (`work/qa/gtour2`, `gtour3m2`, `gtour3m3`). Most other subs draw black with the wrong MAP: the tour is a sample.
- Static sweep: `tools/gfxscan.py ISO OUT` decodes every map tileset of every area (110 distinct blocks, 229 entries,
  `work/qa/gfx/index.tsv`), all reviewed by eye (`work/qa/gfx/pg/`). Tileset formats are in notes.md "Map tilesets".
- Tools: `tools/lua/gfxwho.lua` logs every graphics LZ load (source, VRAM target, ADPCM address, callers);
  `tools/tilefind.py SHOT VRAM x,y,w,h` (needs Pillow: `/usr/local/bin/python3`) names the VRAM tiles under a screen area.

## Not covered yet
- Full-screen cutscene pictures and portraits (row 6 came from the tour only), battle backgrounds and effects,
  sprites: not in the tileset sweep. The tour saw ~80 cutscene / battle screens with no other graphics text.
- Game over screen, ending pictures (status.md: the ending scenes before the roll show no text), the 28 ADPCM
  images whose table entries failed to decode (`work/qa/gfx.log`, areas 04 07 0A 17 1B ...: probably not map areas).
