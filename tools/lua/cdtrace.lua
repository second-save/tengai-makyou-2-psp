-- Log every System Card CD_READ ($E009): sector (_CL/_CH/_DL), count (_AL), target (_DH, _BL/_BH), MPRs, return addresses.
local M = emu.memType.pceMemory
local function mpr(i) return emu.getState()["memoryManager.mpr[" .. i .. "]"] end
emu.addMemoryCallback(function()
  local s = emu.getState()
  local sp = 0x2100 + s["cpu.sp"]
  local st = {}
  for i = 0, 3 do st[#st + 1] = string.format("%04X", emu.read(sp + 2 + i * 2, M) * 256 + emu.read(sp + 1 + i * 2, M) - 2) end
  local z = function(a) return emu.read(0x2000 + a, M) end
  log(string.format("f=%d CD_READ lba=%02X%02X%02X n=%02X dh=%02X bx=%02X%02X mpr2-6=%02X %02X %02X %02X %02X ret=%s",
    FRAME or 0, z(0xFC), z(0xFD), z(0xFE), z(0xF8), z(0xFF), z(0xFB), z(0xFA), mpr(2), mpr(3), mpr(4), mpr(5), mpr(6), table.concat(st, " ")))
end, emu.callbackType.exec, 0xE009)
function on_frame(f) FRAME = f end
