-- Log every {1A} name substitution (69:$536C): slot, the string pointer from $EAD3/$EAD8, the mapped banks and the
-- first bytes at the pointer, plus the caller's return addresses (who set the pointer).
local M = emu.memType.pceMemory
local frames = 0
emu.addEventCallback(function() frames = frames + 1 end, emu.eventType.endFrame)
emu.addMemoryCallback(function()
  local s = emu.getState()
  local y = emu.read(0x536D, M)
  local p = emu.read(0xEAD3 + y, M) | emu.read(0xEAD8 + y, M) << 8
  local t, b, st = {}, {}, {}
  for i = 0, 7 do t[#t + 1] = string.format("%02X", s["memoryManager.mpr[" .. i .. "]"]) end
  for i = 0, 7 do b[#b + 1] = string.format("%02X", emu.read(p + i, M)) end
  for i = 1, 10 do st[#st + 1] = string.format("%02X", emu.read(0x2100 + s["cpu.sp"] + i, M)) end
  log(string.format("NAME f=%d slot=%d ptr=%04X mpr=%s bytes=%s stack=%s", frames, y, p, table.concat(t, " "), table.concat(b, " "), table.concat(st, " ")))
end, emu.callbackType.exec, 0x536C)
