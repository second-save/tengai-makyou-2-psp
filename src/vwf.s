; Variable-width drawing for the half-width font mode (text mode 1, code 05; stock entry 6D:$625A).
; Lives in the free tail of bank 6E, mapped at $8000 by the stub in the tail of bank 6D (see tools/build.py).
; Reuses the game's blitter: glyph rows in $31E1 (16 bits per row), two tiles composed and written by $62B2.
; The cursor $8D/$8E stays in 4-px units for the game's own window logic; `sub` holds the 0-3 px remainder.

.setcpu "huc6280"

ROWS   = $31E1          ; glyph buffer: 2 bytes per row, left byte first
CURX   = $8D
CURY   = $8E
CHAR   = $F9

.segment "STUB"         ; bank 6D, CPU $7FCC
stub:   tma #$10
        pha
        lda #$6E
        tam #$10
        jsr vwf
        pla
        tam #$10
        rts

.segment "DICT"         ; bank 69 tail, CPU $5FE6: called from 6F:$7EA8 in place of JSR $7E5C (next message byte)
dict:   jsr $7E5C       ; bytes $80-$FF = dictionary word 1-128, through the game's own handler of code 1F
        cmp #$80
        bcc d_ret
        sbc #$7F
        plx
        plx
        jmp $7F9E
d_ret:  rts

.segment "VWF"          ; bank 6E tail, CPU $9EB9 while mapped by the stub
vwf:    ldy #$04        ; room check: 6D:$6608 wraps when x + A > (window tiles - 2) * 2 and scrolls when y + Y > (height - 2) * 2.
        lda $93         ; Width 8 px: the last glyph starts by unit 26 and its two tiles stay inside the border (16 px left
        cmp #$06        ; a 3-column menu 16 px in its last column). Height 16 px in windows of 6+ tiles (dialogue paging
        bcs v_room      ; clears the window through this scroll), 8 px in smaller ones (the status bar's 8-px rows)
        ldy #$02
v_room: lda #$02
        jsr $6608
        lda CURX        ; cursor moved by anything but us (newline, position code, new window): drop the remainder
        cmp #$FF
lastx = * - 1
        bne v_moved
        lda CURY
        cmp #$FF
lasty = * - 1
        beq v_same
v_moved: stz sub
v_same:  jsr $62FF       ; 8x8 glyph of CHAR -> ROWS (System Card font, or the game's own digits)
        ldx CHAR
        lda #$08        ; half-width kana and anything else outside the table: full cell
        cpx #$80
        bcs v_got
        lda wtab - $20, x
v_got:   pha             ; high nibble = blank columns on the left, low nibble = advance in px
        lsr a
        lsr a
        lsr a
        lsr a
        sta $00
        lda CURX
        and #$01
        asl a
        asl a
        ora #$00
sub = * - 1
        sec
        sbc $00         ; shift = pixel offset inside the tile - left trim
        beq v_draw
        bmi v_left
        tay
v_r:     clx
v_r1:    lsr ROWS, x
        ror ROWS + 1, x
        inx
        inx
        cpx #$10
        bcc v_r1
        dey
        bne v_r
        bra v_draw
v_left:  tay
v_l:     clx
v_l1:    asl ROWS, x
        inx
        inx
        cpx #$10
        bcc v_l1
        iny
        bne v_l
v_draw:  lda #$FF        ; compose by OR in both tiles (stock masks assume a 4-px grid)
        sta $60E4
        sta $60DD
        jsr $6102       ; BAT position from the cursor
        jsr $62B2       ; two-tile draw, either row parity
        lda #$F0
        sta $60E4
        lda #$0F
        sta $60DD
        pla
        and #$0F
        clc
        adc sub
        tay
        and #$03
        sta sub
        tya
        lsr a
        lsr a
        jsr $6635       ; cursor += A, wrap at the window edge
        lda CURX
        sta lastx
        lda CURY
        sta lasty
        smb1 $9C        ; next newline moves 16 px, as after a kanji
        rts

wtab:                   ; 96 bytes, filled by tools/build.py from the glyph bitmaps
        .res 96, $08
