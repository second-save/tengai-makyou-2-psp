-- Who writes VRAM words LO..HI (word addresses, --var LO= HI=) between frames FROM and TO: logs each distinct writer
-- (bank:pc, first VRAM address, count) and dumps RAM + CPU $2000-$FFFF at the first hit (tag "vram").
-- Tracks the VDC register select ($0000) and MAWR (register 0) itself; assumes auto-increment 1.
local reg, mawr, lo, hi, done, h, order = 0, 0, 0, 0, false, {}, {}
emu.addMemoryCallback(function(a, v)
  if a == 0 then reg = v & 0x1F
  elseif reg == 0 then
    if a == 2 then mawr = (mawr & 0xFF00) | v else mawr = (mawr & 0xFF) | (v << 8) end
  elseif reg == 2 and a == 3 then
    local f = FRAME or 0
    if f >= FROM and f <= TO and mawr >= LO and mawr <= HI then
      local s = emu.getState()
      local pc = s["cpu.pc"]
      local k = string.format("%02X:%04X", s["memoryManager.mpr[" .. (pc >> 13) .. "]"], pc)
      if not h[k] then h[k] = {mawr, 0, f}; order[#order + 1] = k end
      h[k][2] = h[k][2] + 1
      if not done then
        done = true
        dump("vram")
        local p = {}
        for i = 0x2000, 0xFFFF do p[#p + 1] = string.char(emu.read(i, emu.memType.pceMemory)) end
        local fh = io.open(OUT .. "cpuvram.bin", "wb"); fh:write(table.concat(p)); fh:close()
        local t = {}
        for i = 0, 7 do t[#t + 1] = string.format("%02X", s["memoryManager.mpr[" .. i .. "]"]) end
        log(string.format("first hit f=%d pc=%s vram=%04X mpr=%s", f, k, mawr, table.concat(t, " ")))
      end
    end
    mawr = (mawr + 1) & 0xFFFF
  end
end, emu.callbackType.write, 0x0000, 0x0003)
function on_frame(f)
  FRAME = f
  if f == FRAMES - 1 then
    for _, k in ipairs(order) do log(string.format("%s first=%04X n=%d f=%d", k, h[k][1], h[k][2], h[k][3])) end
  end
end
