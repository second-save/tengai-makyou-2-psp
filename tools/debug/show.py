#!/usr/bin/env python3
"""Show messages in the dialogue window without playing to them: one disposable run per message (about 3 s),
one screenshot per page (OUT/<item>/pNN.png).

  show.py --out DIR [--cue work/cd-en/tm2.cue] [--state work/states-en/house.mss] [--jobs 8] [--slow] ITEM...
  show.py --regen [--cue ...] [--state ...]     cold boot and save preload.mss, the house state, battle.mss, town.mss and shop.mss beside
                                                --state (after every rebuild: a state carries the program it was made
                                                with), then check that a message shows from the house state
  show.py --battle --out DIR ITEM...            same in the battle window: from battle.mss, Fight + first target, the
                                                attack line is replaced (the game prints the actor's name before it)

ITEM = sector/group/message (bytes read back from the cue's data.iso by the extractor), or text:... with Python
escapes (text:Hello\\rworld\\x12). Exit 1 if a message did not run to its end.
"""
import argparse, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
PCE = [sys.executable, os.path.join(ROOT, 'tools/pce.py')]
BOOT = '1200:run*10;1500:run*10;1800:run*10;2100:i*10;2400:i*10'   # title -> new game; --mash skips the intro
TALK = '20:down*100;130:left*8;150:down*30'                        # walk into the doorway: the mother speaks
BATTLE = '100:i*4;200:i*4'                                         # msg.lua homes the cursor on Fight; I, I = attack the first enemy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cue', default='work/cd-en/tm2.cue'); ap.add_argument('--state', default='work/states-en/house.mss')
    ap.add_argument('--out'); ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--slow', action='store_true', help='keep the per-glyph delay')
    ap.add_argument('--route', default=TALK, help='inputs that make the game open a message (default: talk to the mother)')
    ap.add_argument('--msg-n', type=int, default=1, help='replace the Nth message the game opens')
    ap.add_argument('--battle', action='store_true', help='show in the battle window (battle.mss beside --state, Fight + target)')
    ap.add_argument('--regen', action='store_true'); ap.add_argument('items', nargs='*')
    a = ap.parse_args()
    if a.regen:
        d, tmp = os.path.dirname(a.state), a.state + '.run'
        pre = os.path.join(d, 'preload.mss')
        lua = [x for n in ('warp.lua', 'battle.lua') for x in ('--script', os.path.join(HERE, n))]
        # the intro's length depends on the build: find the frame of the house load (area 10 sub 11) first, the
        # preload state must come before it or warp.lua never sees a load (a fixed frame broke on the English build)
        subprocess.run(PCE + [a.cue, '--out', tmp, '--frames', '17000', '--route', BOOT, '--mash', '40',
                              '--script', os.path.join(HERE, 'warp.lua'), '--var', 'WARP_N=0'], stdout=subprocess.DEVNULL)
        # map=26: the load that hands control to the player; an earlier house load (map=18) belongs to the intro
        loads = [l for l in open(os.path.join(tmp, 'log.txt')).read().splitlines() if 'area=10 sub=11 map=26' in l]
        if not loads:
            sys.exit('regen: no house load in the first 17000 frames, see %s' % tmp)
        house = int(loads[0].split('f=')[1].split()[0])
        for name, args in (
                ('preload.mss', ['--frames', str(house - 60), '--route', BOOT, '--mash', '40']),   # just before the house loads
                (os.path.basename(a.state), ['--frames', '1700', '--mash', '40', '--state-in', pre]),
                ('battle.mss', ['--frames', '60000', '--state-in', pre, '--var', 'SUB=0x12', '--var', 'MAP=32'] + lua),
                # first village, at the gate; its interiors render only when loaded from here (see notes.md "Scenes")
                ('town.mss', ['--frames', '1500', '--state-in', pre, '--var', 'SUB=0x20', '--var', 'MAP=2', '--var', 'ENT=5',
                              '--script', os.path.join(HERE, 'warp.lua')]),
                # the village shop's buy menu: walk out of the gate, that load goes to sub 0x19, walk to the counter, talk
                ('shop.mss', ['--frames', '1700', '--state-in', os.path.join(d, 'town.mss'), '--route', '10:down*150',
                              '--script', os.path.join(HERE, 'warp.lua'), '--var', 'SUB=0x19', '--var', 'MAP=3', '--var', 'ENT=6',
                              '--script', os.path.join(HERE, 'goto.lua'), '--var', 'START=1000', '--var', "PATH='12,18;18,18'",
                              '--var', "FACE='up'", '--var', 'TALKS=5'])):
            r = subprocess.run(PCE + [a.cue, '--out', tmp, '--state-out'] + args)
            log = os.path.join(tmp, 'log.txt')
            black_ok = name == 'preload.mss' and r.returncode == 3   # taken during the fade before the house load
            if (r.returncode and not black_ok) or (name == 'battle.mss' and 'BATTLE' not in open(log).read()):
                sys.exit('regen: %s failed (exit %d), see %s' % (name, r.returncode, tmp))
            shutil.copy(os.path.join(tmp, 'state.mss'), os.path.join(d, name))
        shutil.rmtree(tmp)
        # the house state is right only if the mother's dialogue opens from it
        rc = subprocess.run([sys.executable, __file__, '--cue', a.cue, '--state', a.state, '--out', tmp, 'text:state ok\\x12']).returncode
        shutil.rmtree(tmp)
        sys.exit(rc)
    iso, blocks = None, {}
    jobs = []
    for it in a.items:
        if it.startswith('text:'):
            data = it[5:].encode().decode('unicode_escape').encode('latin-1')
        elif it.startswith('battle/'):   # a line of the battle stream (use with --battle)
            import extract
            if iso is None:
                iso = open(os.path.join(os.path.dirname(a.cue), 'data.iso'), 'rb').read()
            data = extract.battle(iso)[0][int(it.split('/')[1])]
        else:
            import extract
            sector, group, msg = (int(x) for x in it.split('/'))
            if iso is None:
                iso = open(os.path.join(os.path.dirname(a.cue), 'data.iso'), 'rb').read()
            if sector not in blocks:
                # no validity cut: the default one knows Japanese only (same call as insert.py's read-back)
                blocks[sector] = extract.block(iso, sector * 2048, valid=lambda m: True)
            data = bytes.fromhex(blocks[sector]['groups'][group]['msgs'][msg])
        if b'\x12' not in data:
            data += b'\x12'   # names and battle lines have no wait: without one the window closes before the shot
        jobs.append((it, data))

    def run(i):
        it, data = jobs[i]
        out = os.path.join(a.out, it.replace('/', '_') if not it.startswith('text:') else 'text%d' % i)
        state, route, extra = a.state, a.route, []
        if a.battle:
            state, route, extra = os.path.join(os.path.dirname(a.state), 'battle.mss'), BATTLE, ['--var', 'BATTLE=1']
        cmd = PCE + [a.cue, '--out', out, '--frames', '6000', '--state-in', state, '--route', route, '--var', 'MSG_N=%d' % a.msg_n] + extra + [
                     '--script', os.path.join(HERE, 'msg.lua'), '--var', "HEX='%s'" % data.hex(), '--var', 'FRAME=0']
        subprocess.run(cmd + ([] if a.slow else ['--var', 'FAST=1']), stdout=subprocess.DEVNULL)
        log = os.path.join(out, 'log.txt')
        end = [l for l in open(log).read().splitlines() if l.startswith('END')] if os.path.exists(log) else []
        return it, out, end[0] if end else 'FAILED (no END: the message never finished)'

    bad = 0
    with ThreadPoolExecutor(a.jobs) as ex:
        for it, out, res in ex.map(run, range(len(jobs))):
            print(it[:40], out, res)
            bad += res.startswith('FAILED')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
