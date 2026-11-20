-- Walk in a square from frame WALK_AT (default 900) until a random battle starts, then run BATTLE_WAIT more frames
-- (default 400: the command menu is up) and end the run, so `pce.py --state-out` saves a battle state.
-- A battle = main-program bank 6A mapped at $8000 (mpr4) on 30 samples in a row; the field never maps it there.
-- Use after warp.lua with SUB=0x12 (overworld of the start area). Logs "BATTLE f=...".
local dirs, hits, found = {"down", "right", "up", "left"}, 0, false
function on_frame(f)
  FRAME = f
  if found then return end
  local at = WALK_AT or 900
  if f < at then return end   -- a battle already running in the start state does not count
  if (f - at) % 150 == 0 then ROUTE[#ROUTE + 1] = {f + 1, {dirs[((f - at) // 150) % 4 + 1]}, 150} end
  hits = emu.getState()["memoryManager.mpr[4]"] == 0x6A and hits + 1 or 0
  if hits >= 30 then
    found = true
    for i = #ROUTE, 1, -1 do ROUTE[i] = nil end   -- a direction still held moved the command cursor off the first command
    log("BATTLE f=" .. f)
    FRAMES = f + (BATTLE_WAIT or 400)
  end
end
