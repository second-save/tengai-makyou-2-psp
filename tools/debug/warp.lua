-- Warp: redirect a map load. Every map change runs the loader task in bank 6A, which reads the destination at $697A
-- (area $2BF4 -> event block at sector area*128+2, sub $2BF5, map $2BF6, entrance $323B). This hook rewrites the
-- destination just before it is read, on load number WARP_N (default 1) counted from the start of the run.
-- Globals: AREA, SUB, MAP, ENT (nil = keep), WARP_N. Logs "WARP from a/s/m/e" to log.txt.
local M = emu.memType.pceMemory
local n = 0
local function set(a, v) if v then emu.write(a, v, M) end end
emu.addMemoryCallback(function()
  if emu.getState()["memoryManager.mpr[3]"] ~= 0x6A then return end
  n = n + 1
  log(string.format("LOAD %d f=%d area=%02X sub=%02X map=%02X ent=%02X", n, FRAME or 0,
    emu.read(0x2BF4, M), emu.read(0x2BF5, M), emu.read(0x2BF6, M), emu.read(0x323B, M)))
  if n == (WARP_N or 1) then
    set(0x2BF4, AREA); set(0x2BF5, SUB); set(0x2BF6, MAP); set(0x323B, ENT)
    log("WARP")
  end
end, emu.callbackType.exec, 0x697A)
function on_frame(f) FRAME = f end
