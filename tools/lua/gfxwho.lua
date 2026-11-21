-- Log every graphics LZ block load (69:$4681/$4683, source pointer in zp $10/$11, header = u16 word count, bit 15 =
-- ring B): frame, VRAM target ($12/$13 when set by the caller), MPRs, source and its first 16 bytes (to find on disc).
local M = emu.memType.pceMemory
local function hook(pc)
  emu.addMemoryCallback(function()
    local s = emu.getState()
    if s["memoryManager.mpr[2]"] ~= 0x69 then return end
    local src = emu.read(0x2010, M) | emu.read(0x2011, M) << 8
    local b = {}
    for i = 0, 15 do b[#b + 1] = string.format("%02X", emu.read(src + i, M)) end
    local m = {}
    for i = 0, 7 do m[#m + 1] = string.format("%02X", s["memoryManager.mpr[" .. i .. "]"]) end
    local sp = 0x2100 + s["cpu.sp"]
    local ret = {}
    for i = 0, 3 do ret[#ret + 1] = string.format("%04X", emu.read(sp + 2 + i * 2, M) * 256 + emu.read(sp + 1 + i * 2, M) - 2) end
    log(string.format("GFX f=%d pc=%04X src=%04X mpr=%s bytes=%s ret=%s", FRAME or 0, pc, src, table.concat(m, " "),
      table.concat(b), table.concat(ret, " ")))
  end, emu.callbackType.exec, pc)
end
hook(0x4681); hook(0x4683)
-- 69:$46C4 = LZ init with A:X = source; logs the VRAM address ($12/$13) and word count ($2E3C hi, header lo)
emu.addMemoryCallback(function()
  local s = emu.getState()
  if s["memoryManager.mpr[2]"] ~= 0x69 then return end
  local sp = 0x2100 + s["cpu.sp"]
  local ret = {}
  for i = 0, 5 do ret[#ret + 1] = string.format("%04X", emu.read(sp + 2 + i * 2, M) * 256 + emu.read(sp + 1 + i * 2, M) - 2) end
  log(string.format("INIT f=%d adpcm=%02X%02X src=%02X%02X vram=%02X%02X hi=%02X mpr2-6=%02X %02X %02X %02X %02X ret=%s", FRAME or 0, emu.read(0x2029, M), emu.read(0x2028, M),
    s["cpu.a"], s["cpu.x"], emu.read(0x2013, M), emu.read(0x2012, M), emu.read(0x2E3C, M), s["memoryManager.mpr[2]"], s["memoryManager.mpr[3]"],
    s["memoryManager.mpr[4]"], s["memoryManager.mpr[5]"], s["memoryManager.mpr[6]"], table.concat(ret, " ")))
end, emu.callbackType.exec, 0x46C4)
