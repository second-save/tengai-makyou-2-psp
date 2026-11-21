; Ending staff roll (program 0x9E, loaded at bank $69 = CPU $4000): ASCII cells.
; The roll draws one 16x16 cell per 2-byte code ($F9 = first byte, $F8 = second) into the 32-byte buffer $2DEE
; (16 rows x 2 bytes, left byte first) through 6A:$650C: 01 nn = the game's own glyph nn, anything else = System Card
; EX_GETFNT (16x16 SJIS). This adds: two bytes 20-7E = two 8x8 System Card ASCII glyphs side by side (rows 4-11),
; so a line holds 32 characters instead of 16. 6A:$650C becomes JMP cell (see tools/build.py).

.setcpu "huc6280"

BUF  = $2DEE
PTR  = $1E              ; scratch, also used by the game's own glyph path

.segment "ROLL"         ; bank 6A tail (FF in the program), CPU $7F00
cell:   lda $F9
        cmp #$01
        bne c_ascii
        jmp $6519       ; the game's own glyph
c_ascii:
        cmp #$20
        bcc c_sjis
        cmp #$7F
        bcs c_sjis
        tma #$10        ; System Card bank 1 at $8000: 8x8 font, glyph c at $8000 + c * 8
        pha
        lda #$01
        tam #$10
        clx
        cla
c_clr:  sta BUF,x
        inx
        cpx #$20
        bne c_clr
        lda $F9
        ldx #$08        ; row 4, left byte
        jsr put
        lda $F8
        ldx #$09        ; row 4, right byte
        jsr put
        pla
        tam #$10
        rts
c_sjis: jsr $3836       ; as the stock code: EX_GETFNT through the BIOS call trampoline
        .byte $2C, $60, $E0
        rts

put:    stz PTR+1
        asl a
        rol PTR+1
        asl a
        rol PTR+1
        asl a
        rol PTR+1
        sta PTR
        lda PTR+1
        ora #$80
        sta PTR+1
        cly
p_row:  lda (PTR),y
        sta BUF,x
        inx
        inx
        iny
        cpy #$08
        bne p_row
        rts
