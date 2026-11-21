# Decisions

## Names in the status bar (2026-11-20)
- Ruling (user, earlier session): shorter names where full ones would overlap or overflow.
- Applied: the status bar / battle prompt name list (6B:$6C55, moved to $6C3D) uses Manji, Kabuki, Goku, Kinu
  (32 px each after moving the HP label from +24 to +32 px). Full names (Manjimaru, Gokuraku...) everywhere else.
- Field menu kinds use "Item" (singular, DS precedent) where "Items" did not fit; battle menu "Scroll" and "Plans".

## Status ailments (2026-11-20)
- The 3-kana ailment codes (ひんし まひ こおり ...) became 3-letter codes: Low Par Ice Slp Cnf Fgt Acd Psn.
- The coloured ailment words have 4 bytes each: Weak Numb Iced Doze Daze Mute, "Acd" for 酸; 毒 keeps its kanji
  (2 bytes, and the list's access method is unknown so entries cannot borrow room). Revisit if the list base is found.
- Storage menu: "Put" / "Take", money lines "Own" / "Box" + Ryo (Cash / Bank + Ryo do not fit).

## Credits and title logo (2026-11-21)
- Options: credits in English / kept Japanese / staff roll only; logo kept / redrawn in English.
- Ruling (user): credits in English (opening graphics card "制作・総指揮 工藤裕司" and the ending staff roll at
  iso 0x279F000), names romanized. Title logo 天外魔境 II stays kanji (FAR EAST OF EDEN is already above it).

## Letter picture (2026-11-21)
- Options: redraw the "卍丸さん江" letter picture (area 0x1C, graphics.md row 6) in English / keep it as art.
- Ruling (user): keep the kanji as artwork; the caption already explains it.

## Shop signboards and money-changer board (2026-11-21)
- Options: short English words (ARMS / INN ...) / pictograms / keep the kanji (graphics.md row 4).
- Ruling (user): keep the kanji as scenery; the shop's own title text names it. Same for the money-changer board
  両売替… (graphics.md row 5).
