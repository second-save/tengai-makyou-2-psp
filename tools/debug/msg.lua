-- Show any message in whatever window the game opens next: when message open number MSG_N (default 1) starts its
-- LZ stream, overwrite the stream in RAM with HEX (raw message bytes as insert.py encodes them, without the final 00),
-- stored as LZ literals. The run is disposable: neighbouring streams of the block are overwritten.
-- Globals: HEX (string), MSG_N. Logs "MSG group msg src".
local M = emu.memType.pceMemory
local n, skip = 0, nil
emu.addMemoryCallback(function()
  local s = emu.getState()
  if s["memoryManager.mpr[3]"] ~= 0x6F then return end
  n = n + 1
  if n == (MSG_N or 1) then skip = s["cpu.a"] end
end, emu.callbackType.exec, 0x7E6D)
emu.addMemoryCallback(function()
  if not skip then return end
  local s = emu.getState()
  local src = s["cpu.a"] * 256 + s["cpu.x"]
  local raw = {}
  for i = 1, skip do raw[#raw + 1] = 0 end
  for h in HEX:gmatch("%x%x") do raw[#raw + 1] = tonumber(h, 16) end
  raw[#raw + 1] = 0
  local p = src
  for i = 1, #raw do
    if i % 8 == 1 then emu.write(p, 0xFF, M); p = p + 1 end  -- flag byte: 8 literals
    emu.write(p, raw[i], M); p = p + 1
  end
  log(string.format("MSG group=%02X msg=%02X src=%04X bytes=%d", emu.read(0x20DA, M), skip, src, #raw))
  skip = nil
  active = true
end, emu.callbackType.exec, 0x3C77)

-- Once the forced message runs: one shot per page (pNN.png) when the interpreter reaches the wait code (69:$52D3),
-- then press I; stop the run when the message ends (69:$51BF reads 00). FAST=1 draws without the per-glyph delay.
local page, shoot_at, stop_at = 0, nil, nil
-- SHOT_DELAY: 3 frames was too early, the last glyphs were not on screen yet
emu.addMemoryCallback(function() if active and not shoot_at then shoot_at = FRAME + (SHOT_DELAY or 10) end end, emu.callbackType.exec, 0x52D3)
emu.addMemoryCallback(function()
  if active and emu.getState()["cpu.a"] == 0 then active = false; stop_at = FRAME + 20 end
end, emu.callbackType.exec, 0x51BF)
function on_frame(f)
  FRAME = f
  if FAST and active then emu.write(0xE3C8, 0, M) end
  if shoot_at and f >= shoot_at then
    shot(string.format("p%02d.png", page)); page = page + 1
    ROUTE[#ROUTE + 1] = {f + 2, {"i"}, 6}
    shoot_at = nil
  end
  if stop_at and f >= stop_at then log("END pages=" .. page); FRAMES = f end
end
