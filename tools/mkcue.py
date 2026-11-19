#!/usr/bin/env python3
"""Make a .cue around a data-track .iso so a PC Engine CD emulator (Mesen) can boot it.

  mkcue.py HCD.hcd DATA.iso OUTDIR      -> OUTDIR/tm2.cue

Audio tracks are silence (sparse zero files): QA only needs the right track layout.
shortcut: no music in emulator QA; decode the .at3 tracks if a sound check is ever needed.
"""
import os, sys


def msf(frames):
    return '%02d:%02d:%02d' % (frames // 4500, frames // 75 % 60, frames % 75)


def main(hcd, iso, outdir):
    os.makedirs(outdir, exist_ok=True)
    tracks = []
    for line in open(hcd).read().splitlines():
        f = line.split(',')
        if f[0].startswith('track'):
            tracks.append((f[1].strip(), int(f[3]) - 150, int(f[4])))  # type, LBA, sectors
    # a cue places each FILE after the previous one, so the silence is cut where the data track sits
    cue, base, part = [], 0, 0
    for n, (kind, lba, size) in enumerate(tracks, 1):
        if kind == 'code':
            link = os.path.join(outdir, 'data.iso')  # Mesen joins the cue's folder and the FILE name
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(os.path.abspath(iso), link)
            cue += ['FILE "data.iso" BINARY', f'  TRACK {n:02d} MODE1/2048', '    INDEX 01 00:00:00']
            base, part = lba + size, part + 1
            continue
        if not cue or cue[-1].endswith('00:00:00') and 'MODE1' in cue[-2]:
            nxt = next((t[1] for t in tracks[n:] if t[0] == 'code'), tracks[-1][1] + tracks[-1][2])
            name = f'silence{part}.bin'
            with open(os.path.join(outdir, name), 'wb') as f:
                f.truncate((nxt - base) * 2352)
            cue += [f'FILE "{name}" BINARY']
        cue += [f'  TRACK {n:02d} AUDIO', f'    INDEX 01 {msf(lba - base)}']
    open(os.path.join(outdir, 'tm2.cue'), 'w').write('\n'.join(cue) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
