-- Log reads of CPU range RLO..RHI (globals) while the window's MPR holds bank RBANK (any bank if unset):
-- frame, address, PC, MPR2-5, and the first 6 return addresses on the stack. One line per distinct PC per frame.
local seen = {}
local function mpr(i) return emu.getState()["memoryManager.mpr[" .. i .. "]"] end
-- RLO/RHI are offsets inside an 8K bank (0..0x1FFF) when RBANK is set: the range is watched in every window $2000-$FFFF.
local function cb(addr)
  if RBANK and mpr(addr >> 13) ~= RBANK then return end
  local s = emu.getState()
  local k = (FRAME or 0) .. ":" .. s["cpu.pc"]
  if seen[k] then return end
  seen[k] = true
  local st = {}
  for i = 1, 6 do st[#st + 1] = string.format("%02X", emu.read(0x2100 + s["cpu.sp"] + i, emu.memType.pceMemory)) end
  log(string.format("f=%d R %04X pc=%04X mpr2-5=%02X %02X %02X %02X stack=%s", FRAME or 0, addr, s["cpu.pc"],
    mpr(2), mpr(3), mpr(4), mpr(5), table.concat(st, " ")))
end
if RBANK then
  for w = 1, 7 do emu.addMemoryCallback(cb, emu.callbackType.read, w * 0x2000 + RLO, w * 0x2000 + RHI) end
else
  emu.addMemoryCallback(cb, emu.callbackType.read, RLO, RHI)
end
function on_frame(f) FRAME = f end
