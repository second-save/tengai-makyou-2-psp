#!/usr/bin/env python3
"""Show messages in the dialogue window without playing to them: one disposable run per message (about 3 s),
one screenshot per page (OUT/<item>/pNN.png).

  show.py --out DIR [--cue work/cd-en/tm2.cue] [--state work/states-en/house.mss] [--jobs 8] [--slow] ITEM...
  show.py --regen [--cue ...] [--state ...]     cold boot to the first house and save the state (after every rebuild:
                                                a state carries the program it was made with)

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cue', default='work/cd-en/tm2.cue'); ap.add_argument('--state', default='work/states-en/house.mss')
    ap.add_argument('--out'); ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--slow', action='store_true', help='keep the per-glyph delay')
    ap.add_argument('--regen', action='store_true'); ap.add_argument('items', nargs='*')
    a = ap.parse_args()
    if a.regen:
        tmp = a.state + '.run'
        r = subprocess.run(PCE + [a.cue, '--out', tmp, '--frames', '16000', '--route', BOOT, '--mash', '40', '--state-out'])
        if r.returncode:
            sys.exit(r.returncode)
        shutil.copy(os.path.join(tmp, 'state.mss'), a.state)
        shutil.rmtree(tmp)
        return
    iso, blocks = None, {}
    jobs = []
    for it in a.items:
        if it.startswith('text:'):
            data = it[5:].encode().decode('unicode_escape').encode('latin-1')
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
        cmd = PCE + [a.cue, '--out', out, '--frames', '6000', '--state-in', a.state, '--route', TALK,
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
