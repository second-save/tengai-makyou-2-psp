-- Walk the player to waypoints by RAM position, then face a direction and press I (talk / examine).
-- Globals: PATH = "x,y;x,y" in map units (X = $2085, Y = $2087, 4 px each), FACE = "up"|"down"|"left"|"right" (optional),
-- START (frame to start, default 300: the player cannot move earlier after a map load), TALKS (I presses, default 3).
-- Logs "AT x,y f=..." at each waypoint and "STUCK x,y" when the player has not moved for 60 frames (wall or NPC).
local M = emu.memType.pceMemory
local pts = {}
for x, y in string.gmatch(PATH or "", "(%d+),(%d+)") do pts[#pts + 1] = {tonumber(x), tonumber(y)} end
local i, last, still, talk_at = 1, nil, 0, nil
function on_frame(f)
  FRAME = f
  if f < (START or 300) then return end
  local x, y = emu.read(0x2085, M), emu.read(0x2087, M)
  if i <= #pts then
    local tx, ty = pts[i][1], pts[i][2]
    local key = x < tx and "right" or x > tx and "left" or y < ty and "down" or y > ty and "up" or nil
    if not key then log(string.format("AT %d,%d f=%d", x, y, f)); i = i + 1; return end
    still = (last and last[1] == x and last[2] == y) and still + 1 or 0
    last = {x, y}
    if still == 60 then log(string.format("STUCK %d,%d f=%d", x, y, f)) end
    ROUTE[#ROUTE + 1] = {f + 1, {key}, 1}
  elseif not talk_at then
    talk_at = f + 2
    if FACE then ROUTE[#ROUTE + 1] = {f + 1, {FACE}, 2} end
    for n = 0, (TALKS or 3) - 1 do ROUTE[#ROUTE + 1] = {talk_at + 4 + n * 100, {"i"}, 4} end
  end
end
