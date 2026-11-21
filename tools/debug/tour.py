#!/usr/bin/env python3
"""Graphics tour: warp to many area/sub pairs from town.mss and shoot each, for the graphics-text survey.

  tour.py --out DIR [--subs 10] [--map 1] [--frames 1800] [--jobs 8] [AREA...]   (hex; default: every area in scenes.py)

Writes DIR/<area>_<sub>/f*.png and one contact sheet per run (DIR/sheets/<area>_<sub>.png).
"""
import argparse, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import scenes

SKILL = os.environ.get('TRANSLATE_SKILL', os.path.expanduser('~/.claude/skills/translate-retro-game'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--cue', default='work/cd-en/tm2.cue')
    ap.add_argument('--state', default='work/states-en/town.mss'); ap.add_argument('--subs', default='10')
    ap.add_argument('--map', default='1'); ap.add_argument('--frames', type=int, default=1800)
    ap.add_argument('--jobs', type=int, default=8); ap.add_argument('areas', nargs='*')
    a = ap.parse_args()
    iso = open(os.path.join(os.path.dirname(a.cue), 'data.iso'), 'rb').read()
    areas = [int(x, 16) for x in a.areas] or [x for x in range(0x400) if scenes.events(iso, x)]
    jobs = [(ar, int(s, 16)) for ar in areas for s in a.subs.split(',')]
    os.makedirs(os.path.join(a.out, 'sheets'), exist_ok=True)

    def run(job):
        ar, sub = job
        name = '%02X_%02X' % job
        d = os.path.join(a.out, name)
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools/pce.py'), a.cue, '--out', d, '--frames', str(a.frames),
                        '--state-in', a.state, '--route', '10:down*150', '--script', os.path.join(HERE, 'warp.lua'),
                        '--var', 'AREA=%d' % ar, '--var', 'SUB=%d' % sub, '--var', 'MAP=%s' % a.map,
                        '--shot-every', str(a.frames // 3), '--timeout', '120'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        subprocess.run([sys.executable, os.path.join(SKILL, 'scripts/sheet.py'), d, '--out',
                        os.path.join(a.out, 'sheets', name + '.png')], stdout=subprocess.DEVNULL)
        return name

    with ThreadPoolExecutor(a.jobs) as ex:
        for i, name in enumerate(ex.map(run, jobs)):
            print(i + 1, len(jobs), name, flush=True)


if __name__ == '__main__':
    main()
