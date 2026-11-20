-- Log every use of the stream LZSS: init ($3C77 ring A, $3D52 ring B) with the source pointer, the bank
-- mapped at it, the caller, and how many bytes were then pulled ($3C8D / $3D62) before the next init.
local n, cur = 0, nil
local function mpr(i) return emu.getState()["memoryManager.mpr[" .. i .. "]"] end
local function flush() if cur then log(cur .. string.format(" out=%d", n)) end; cur = nil; n = 0 end
local function ret()
  local s = emu.getState()
  local sp = 0x2100 + s["cpu.sp"]
  local lo, hi = emu.read(sp + 1, emu.memType.pceMemory), emu.read(sp + 2, emu.memType.pceMemory)
  local lo2, hi2 = emu.read(sp + 3, emu.memType.pceMemory), emu.read(sp + 4, emu.memType.pceMemory)
  return string.format("ret=%04X ret2=%04X", hi * 256 + lo - 2, hi2 * 256 + lo2 - 2), s
end
emu.addMemoryCallback(function()
  flush()
  local r, s = ret()
  local a, x = s["cpu.a"], s["cpu.x"]
  cur = string.format("f=%d A src=%02X%02X bank=%02X %s", FRAME or 0, a, x, mpr(a >> 5), r)
end, emu.callbackType.exec, 0x3C77)
emu.addMemoryCallback(function()
  local r, s = ret()
  local a, x = s["cpu.a"], s["cpu.x"]
  log(string.format("   ringB init f=%d src=%02X%02X bank=%02X %s", FRAME or 0, a, x, mpr(a >> 5), r))
end, emu.callbackType.exec, 0x3D52)
emu.addMemoryCallback(function() n = n + 1 end, emu.callbackType.exec, 0x3C8D)
emu.addMemoryCallback(function() n = n + 1 end, emu.callbackType.exec, 0x3D62)
function on_frame(f) FRAME = f; if f == FRAMES - 1 then flush() end end
