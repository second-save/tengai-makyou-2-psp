-- Histogram of the PCs (with the bank mapped there) that write the VDC data port, between frames FROM and TO.
-- Also dumps RAM + the CPU-visible $2000-$FFFF at the first write after FROM (tag "draw").
local h, done = {}, false
emu.addMemoryCallback(function()
  local f = FRAME or 0
  if f < FROM or f > TO then return end
  local s = emu.getState()
  local pc = s["cpu.pc"]
  local k = string.format("%02X:%04X", s["memoryManager.mpr[" .. (pc >> 13) .. "]"], pc)
  h[k] = (h[k] or 0) + 1
  if not done and pc >= 0x4000 then
    done = true
    dump("draw")
    local p = {}
    for i = 0x2000, 0xFFFF do p[#p + 1] = string.char(emu.read(i, emu.memType.pceMemory)) end
    local fh = io.open(OUT .. "cpudraw.bin", "wb"); fh:write(table.concat(p)); fh:close()
    local t = {}
    for i = 0, 7 do t[#t + 1] = string.format("%02X", s["memoryManager.mpr[" .. i .. "]"]) end
    log("first write f=" .. f .. " pc=" .. k .. " mpr=" .. table.concat(t, " "))
  end
end, emu.callbackType.write, 0x0002, 0x0003)
function on_frame(f)
  FRAME = f
  if f == FRAMES - 1 then for k, v in pairs(h) do log(k .. " " .. v) end end
end
