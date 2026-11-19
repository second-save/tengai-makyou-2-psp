#!/usr/bin/env python3
"""Headless PC Engine CD run in Mesen: scripted input, screenshots, RAM dumps, extra Lua.

  pce.py CUE --out DIR --frames N [--route "600:run*10;900:i*5"] [--mash N] [--shots 600,1200 | --shot-every N]
         [--dump 1200,...] [--state-in F] [--state-out F] [--script x.lua] [--var NAME=LUA]

Route step "FRAME:button[+button]*HOLD". Buttons: i ii select run up down left right.
--dump writes ram<frame>.bin (0x2000 work RAM + 0x10000 CD RAM + 0x30000 Super CD RAM) and vram<frame>.bin.
Exit 0 ok, 2 Lua error, 3 black final frame, 124 timeout.
"""
import argparse, json, os, struct, subprocess, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'tools/mesen/Mesen.app/Contents/MacOS/Mesen')

LUA = r'''
local frame, saving, saved = 0, false, false
local function wr(name, data) local f = io.open(OUT .. name, "wb"); f:write(data); f:close() end
local function grab(t, n) local p = {}; for i = 0, n - 1 do p[#p + 1] = string.char(emu.read(i, t)) end; return table.concat(p) end
function shot(name) wr(name, emu.takeScreenshot()) end
function dump(tag)
  wr("ram" .. tag .. ".bin", grab(emu.memType.pceWorkRam, 0x2000) .. grab(emu.memType.pceCdromRam, 0x10000) .. grab(emu.memType.pceCardRam, 0x30000))
  wr("vram" .. tag .. ".bin", grab(emu.memType.pceVideoRam, 0x10000))
end
function log(s) local f = io.open(OUT .. "log.txt", "a"); f:write(s .. "\n"); f:close() end
local ok, err = pcall(function()
  if STATE_IN then
    local done = false
    -- Mesen only allows savestate calls inside an exec callback
    emu.addMemoryCallback(function() if not done then done = true; local f = io.open(STATE_IN, "rb"); emu.loadSavestate(f:read("*a")); f:close() end end, emu.callbackType.exec, 0, 0xFFFF)
  end
  emu.addEventCallback(function()
    local b = {}
    for _, s in ipairs(ROUTE) do if frame >= s[1] and frame < s[1] + s[3] then for _, k in ipairs(s[2]) do b[k] = true end end end
    if MASH > 0 and frame % MASH < 4 then b[MASH_KEY] = true end
    emu.setInput(b, 0)
  end, emu.eventType.inputPolled)
  emu.addEventCallback(function()
    frame = frame + 1
    if SHOTS[frame] or (SHOT_EVERY > 0 and frame % SHOT_EVERY == 0) then shot(string.format("f%06d.png", frame)) end
    if DUMPS[frame] then dump(tostring(frame)) end
    if on_frame then on_frame(frame) end
    if frame >= FRAMES then
      shot("final.png")
      if STATE_OUT then
        if not saving then saving = true; emu.addMemoryCallback(function() if not saved then saved = true; wr("state.mss", emu.createSavestate()) end end, emu.callbackType.exec, 0, 0xFFFF) end
        if saved then emu.stop(0) end
      else emu.stop(0) end
    end
  end, emu.eventType.endFrame)
end)
if not ok then wr("lua_error.txt", tostring(err)); emu.stop(2) end
'''


def lua_set(xs):
    return '{' + ','.join(f'[{x}]=true' for x in xs) + '}'


def black(png):
    d = open(png, 'rb').read()
    i, idat = 8, b''
    while i < len(d):
        n, t = struct.unpack('>I4s', d[i:i + 8])
        if t == b'IDAT':
            idat += d[i + 8:i + 8 + n]
        i += 12 + n
    raw = zlib.decompress(idat)
    return len(set(raw[1000:200000:7])) < 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('--out', required=True); ap.add_argument('--frames', type=int, required=True)
    ap.add_argument('--route', default=''); ap.add_argument('--mash', type=int, default=0); ap.add_argument('--mash-key', default='i')
    ap.add_argument('--shots', default=''); ap.add_argument('--shot-every', type=int, default=0); ap.add_argument('--dump', default='')
    ap.add_argument('--state-in'); ap.add_argument('--state-out', action='store_true', help='write OUT/state.mss at the end')
    ap.add_argument('--script', action='append', default=[]); ap.add_argument('--var', action='append', default=[])
    ap.add_argument('--timeout', type=int, default=600)
    a = ap.parse_args()
    out = os.path.abspath(a.out) + '/'
    os.makedirs(out, exist_ok=True)
    for n in [f for f in os.listdir(out) if f.endswith('.png') or f in ('lua_error.txt', 'log.txt')]:
        os.remove(out + n)  # stale shots from an earlier run ended up in new sheets
    cfgp = os.path.join(os.path.dirname(EXE), 'settings.json')
    cfg = json.load(open(cfgp, encoding='utf-8-sig')) if os.path.exists(cfgp) else {}
    was = json.dumps(cfg)
    cfg.setdefault('Debug', {}).setdefault('ScriptWindow', {})['AllowIoOsAccess'] = True
    cfg.setdefault('PcEngine', {}).setdefault('Port1', {}).setdefault('Type', 'PceController')
    cfg.setdefault('ConfigUpgrade', 1)
    if json.dumps(cfg) != was:   # parallel runs: rewriting it every time let another run read a half-written file
        json.dump(cfg, open(cfgp + '.tmp', 'w'), indent=2)
        os.replace(cfgp + '.tmp', cfgp)
    route = []
    for step in filter(None, (s.strip() for s in a.route.split(';'))):
        fr, rest = step.split(':')
        keys, _, hold = rest.partition('*')
        route.append('{%d,{%s},%d}' % (int(fr), ','.join(f'"{k}"' for k in keys.split('+')), int(hold or 6)))
    head = [f'OUT = {json.dumps(out)}', f'FRAMES = {a.frames}', f'ROUTE = {{{",".join(route)}}}', f'MASH = {a.mash}',
            f'MASH_KEY = "{a.mash_key}"', f'SHOTS = {lua_set(a.shots.split(",") if a.shots else [])}',
            f'SHOT_EVERY = {a.shot_every}', f'DUMPS = {lua_set(a.dump.split(",") if a.dump else [])}',
            f'STATE_IN = {json.dumps(os.path.abspath(a.state_in)) if a.state_in else "nil"}',
            f'STATE_OUT = {"true" if a.state_out else "nil"}'] + [v.replace('=', ' = ', 1) for v in a.var]
    body = ''.join(open(s, encoding='utf-8').read() + '\n' for s in a.script)
    lua = out + '_run.lua'
    open(lua, 'w', encoding='utf-8').write('\n'.join(head) + '\n' + body + LUA)
    try:
        p = subprocess.run([EXE, '--testRunner', f'--timeout={a.timeout}', os.path.abspath(a.cue), lua],
                           stdout=open(out + 'mesen.log', 'w'), stderr=subprocess.STDOUT, timeout=a.timeout + 30)
        code = p.returncode
    except subprocess.TimeoutExpired:
        code = 124
    if os.path.exists(out + 'lua_error.txt'):
        print(open(out + 'lua_error.txt').read(), file=sys.stderr)
        code = 2
    elif code == 0 and (not os.path.exists(out + 'final.png') or black(out + 'final.png')):
        code = 3
    print('exit', code)
    sys.exit(code)


if __name__ == '__main__':
    main()
