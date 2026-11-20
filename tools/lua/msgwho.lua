-- Log every message open (6F:$7E6D, A = message, $DA = group) and every 71:$752A string print (pointer $F659/$F65A),
-- with the frame, the mapped banks and the return addresses on the stack.
local function stack(s)
  local st = {}
  for i = 1, 8 do st[#st + 1] = string.format("%02X", emu.read(0x2100 + s["cpu.sp"] + i, emu.memType.pceMemory)) end
  return table.concat(st, " ")
end
local frames = 0   -- own count: FRAME is only set when battle.lua runs too
emu.addEventCallback(function() frames = frames + 1 end, emu.eventType.endFrame)
local function mpr(s, i) return s["memoryManager.mpr[" .. i .. "]"] end
emu.addMemoryCallback(function()
  local s = emu.getState()
  if mpr(s, 3) ~= 0x6F then return end
  log(string.format("OPEN f=%d grp=%d msg=%d mpr2-4=%02X %02X %02X stack=%s", frames, emu.read(0x20DA, emu.memType.pceMemory),
    s["cpu.a"], mpr(s, 2), mpr(s, 3), mpr(s, 4), stack(s)))
end, emu.callbackType.exec, 0x7E6D)
emu.addMemoryCallback(function()
  local s = emu.getState()
  if mpr(s, 3) ~= 0x71 then return end
  local lo, hi = emu.read(0xF659, emu.memType.pceMemory), emu.read(0xF65A, emu.memType.pceMemory)
  log(string.format("PRINT f=%d ptr=%02X%02X stack=%s", frames, hi, lo, stack(s)))
end, emu.callbackType.exec, 0x752A)
