-- At each LZ init: all MPRs, registers, the 12 stack bytes above SP, and a RAM dump (once).
local done = false
emu.addMemoryCallback(function()
  local s = emu.getState()
  local t = {}
  for i = 0, 7 do t[#t + 1] = string.format("%02X", s["memoryManager.mpr[" .. i .. "]"]) end
  local st = {}
  for i = 1, 12 do st[#st + 1] = string.format("%02X", emu.read(0x2100 + s["cpu.sp"] + i, emu.memType.pceMemory)) end
  log(string.format("A=%02X X=%02X Y=%02X mpr=%s stack=%s", s["cpu.a"], s["cpu.x"], s["cpu.y"], table.concat(t, " "), table.concat(st, " ")))
  if not done then done = true; dump("msg") end
end, emu.callbackType.exec, 0x3C77)
