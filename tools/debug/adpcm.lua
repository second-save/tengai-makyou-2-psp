-- Load a 64K ADPCM image (ADPCM_IMG = path) into ADPCM RAM on the first frame: puts a rebuilt area's battle data
-- (enemy records, battle text) under an old battle state. The game re-reads the enemy record each time it prints one.
-- Uses its own frame callback, so it combines with scripts that define on_frame (battle.lua).
local done = false
emu.addEventCallback(function()
  if done then return end
  done = true
  local fh = assert(io.open(ADPCM_IMG, "rb"))
  local data = fh:read("a")
  fh:close()
  for i = 1, #data do emu.write(i - 1, data:byte(i), emu.memType.pceAdpcmRam) end
  log("ADPCM loaded " .. #data)
end, emu.eventType.startFrame)
