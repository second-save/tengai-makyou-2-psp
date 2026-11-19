-- Replace the next expanded message with TEXT (a Lua string of raw interpreter bytes) the first time the text
-- interpreter fetches a byte ($51CD) after frame FROM. Experiments only: font modes, widths, control codes.
local done = false
emu.addMemoryCallback(function()
  if done or (FRAME or 0) < FROM then return end
  done = true
  local p = emu.read(0x2095, emu.memType.pceMemory) + emu.read(0x2096, emu.memType.pceMemory) * 256
  for i = 1, #TEXT do emu.write(p + i - 1, TEXT:byte(i), emu.memType.pceMemory) end
  emu.write(p + #TEXT, 0, emu.memType.pceMemory)
  log(string.format("poked %d bytes at %04X", #TEXT, p))
end, emu.callbackType.exec, 0x51CD)
function on_frame(f) FRAME = f end
