-- Dump ADPCM RAM (64K) to OUT/adpcm<frame>.bin at frame AT (--var AT=N), and log every System Card AD_READ ($E036):
-- ADPCM address (_CL/_CH), destination (_BL/_BH), length (_AL/_AH), caller.
local M = emu.memType.pceMemory
emu.addMemoryCallback(function()
  local s = emu.getState()
  local z = function(a) return emu.read(0x2000 + a, M) end
  local sp = 0x2100 + s["cpu.sp"]
  log(string.format("f=%d AD_READ adpcm=%02X%02X dest=%02X%02X len=%02X%02X ret=%04X", FRAME or 0, z(0xFD), z(0xFC),
    z(0xFB), z(0xFA), z(0xF9), z(0xF8), emu.read(sp + 2, M) * 256 + emu.read(sp + 1, M) - 2))
end, emu.callbackType.exec, 0xE036)
function on_frame(f)
  FRAME = f
  if f == AT then
    local p = {}
    for i = 0, 0xFFFF do p[#p + 1] = string.char(emu.read(i, emu.memType.pceAdpcmRam)) end
    local fh = io.open(OUT .. "adpcm" .. f .. ".bin", "wb"); fh:write(table.concat(p)); fh:close()
  end
end
