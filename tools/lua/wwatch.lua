-- Log writes to CPU range WLO..WHI (globals): frame, address, value, PC, MPR2/3.
local function mpr(i) return emu.getState()["memoryManager.mpr[" .. i .. "]"] end
emu.addMemoryCallback(function(addr, value)
  log(string.format("f=%d W %04X=%02X pc=%04X mpr2-3=%02X %02X", FRAME or 0, addr, value, emu.getState()["cpu.pc"], mpr(2), mpr(3)))
end, emu.callbackType.write, WLO, WHI)
function on_frame(f) FRAME = f end
