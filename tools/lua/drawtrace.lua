-- Text drawing trace: every 12x12 ($6018) / 8x8 ($626B) glyph draw in bank 6D with the character, the cursor and the
-- stack, plus a histogram of the PCs that write the cursor ($8D/$8E).
local function st() return emu.getState() end
local function rd(a) return emu.read(a, emu.memType.pceMemory) end
local n = 0
local function draw(kind)
  return function()
    local s = st()
    if s["memoryManager.mpr[3]"] ~= 0x6D or n >= (MAXLOG or 40) then return end
    n = n + 1
    local t = {}
    for i = 1, 14 do t[#t + 1] = string.format("%02X", rd(0x2100 + s["cpu.sp"] + i)) end
    log(string.format("%s f=%d ch=%02X%02X x=%02X y=%02X org=%02X,%02X 9C=%02X 9E=%02X 9F=%02X mpr4=%02X stack=%s", kind, FRAME or 0,
      rd(0x20F9), rd(0x20F8), rd(0x208D), rd(0x208E), rd(0x2090), rd(0x2091), rd(0x209C), rd(0x209E), rd(0x209F),
      s["memoryManager.mpr[4]"], table.concat(t, " ")))
  end
end
emu.addMemoryCallback(draw("12"), emu.callbackType.exec, 0x6018)
emu.addMemoryCallback(draw("8 "), emu.callbackType.exec, 0x626B)
local h = {}
emu.addMemoryCallback(function()
  local s = st()
  local pc = s["cpu.pc"]
  local k = string.format("w8D %02X:%04X", s["memoryManager.mpr[" .. (pc >> 13) .. "]"], pc)
  h[k] = (h[k] or 0) + 1
end, emu.callbackType.write, 0x208D, 0x208E)
function on_frame(f)
  FRAME = f
  if f == FRAMES - 1 then for k, v in pairs(h) do log(k .. " " .. v) end end
end
