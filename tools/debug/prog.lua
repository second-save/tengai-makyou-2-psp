-- Program swap: the resident loop at $3887 loads program A (sector A*128+2, to bank $69) through $388C and jumps to
-- $4000. This hook replaces A on call number PROG_N (default 1 = the intro, program 0x9F) with PROG.
-- Programs: 0x01 main game, 0x9E ending (staff roll), 0x9F-0xA1 intro, 0xA8-0xA9 title. Logs every load to log.txt.
local M = emu.memType.pceMemory
local n = 0
emu.addMemoryCallback(function()
  local s = emu.getState()
  n = n + 1
  log(string.format("PROG %d f=%d A=%02X", n, FRAME or 0, s["cpu.a"]))
  if n == (PROG_N or 1) and PROG then
    s["cpu.a"] = PROG
    emu.setState(s)
    log(string.format("SWAP -> %02X", PROG))
  end
end, emu.callbackType.exec, 0x388C)
function on_frame(f) FRAME = f end
