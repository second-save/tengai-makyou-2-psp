-- Home the battle command cursor on Fight ($2805, copy $282B) for the first frames, so mashing I attacks.
function on_frame(f) if f < 5 then emu.write(0x2805, 0, emu.memType.pceMemory); emu.write(0x282B, 0, emu.memType.pceMemory) end end
