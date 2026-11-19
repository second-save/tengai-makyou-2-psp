-- Trace a map load: between frames T0 and T1 count executed PCs, dump RAM every STEP frames,
-- and log the CPU state (MPR registers) with each dump. Globals: T0, T1, STEP.
local hist, tracing = {}, false
local function state_line()
  local s, out = emu.getState(), {}
  for k, v in pairs(s) do
    if string.find(k, "mpr") or k == "cpu.pc" then out[#out + 1] = k .. "=" .. tostring(v) end
  end
  table.sort(out)
  return table.concat(out, " ")
end
function on_frame(f)
  if f == T0 then
    tracing = true
    emu.addMemoryCallback(function(addr) if tracing then hist[addr] = (hist[addr] or 0) + 1 end end,
      emu.callbackType.exec, 0, 0xFFFF)
  end
  if f >= T0 and f <= T1 and (f - T0) % STEP == 0 then
    dump(tostring(f))
    log(f .. " " .. state_line())
  end
  if f == T1 then
    tracing = false
    local keys = {}
    for k in pairs(hist) do keys[#keys + 1] = k end
    table.sort(keys)
    local fh = io.open(OUT .. "pchist.txt", "w")
    for _, k in ipairs(keys) do fh:write(string.format("%04X %d\n", k, hist[k])) end
    fh:close()
  end
end
