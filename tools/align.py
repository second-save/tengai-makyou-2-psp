#!/usr/bin/env python3
"""Learn the character table by aligning extracted messages with the DS script, and record which DS line each one is.

  align.py BLOCKS.json DS_SCRIPT.json OUT_TABLE.json OUT_MATCH.json

A message is a sequence of glyph keys: "h"/"k" (hiragana/katakana mode, switched by 0E/0F) + hex of a single byte or
an SJIS pair. Dictionary words (1F nn) are expanded first. A message matches a DS line when both have the same number
of glyphs, every glyph already known agrees (compared page by page: match keys are sector/group/message.page) and only one distinct DS text fits; its unknown glyphs then get a vote.
Repeats until nothing new is learned.
"""
import collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import expand

ARG = {0x02, 0x03, 0x10, 0x11, 0x14, 0x15}  # control codes followed by an ASCII decimal argument
HALF = '。「」、・をぁぃぅぇぉゃゅょっーあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん゛゜'  # 0xA1..0xDF


def glyphs(m):
    """Glyph keys of an expanded message, control codes dropped."""
    return [x for p in pages(m) for x in p]


def pages(m):
    """Glyph keys per page: the DS script has one line per page (split at the wait code 12)."""
    res, out, i, mode = [], [], 0, 'h'
    while i < len(m):
        c = m[i]
        i += 1
        if c == 0x0E:
            mode = 'k'
        elif c == 0x0F:
            mode = 'h'
        elif c in ARG:
            while i < len(m) and 0x30 <= m[i] <= 0x39:
                i += 1
        elif c == 0x1B:  # one raw argument byte
            i += 1
        elif c == 0x12:
            res.append(out)
            out = []
        elif c < 0x20:
            pass
        elif (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEA) and i < len(m):
            out.append('%02x%02x' % (c, m[i]))
            i += 1
        else:  # only kana change with the mode; the one-byte kanji and signs do not
            out.append('%s%02x' % (mode if 0x61 <= c <= 0x79 or c >= 0xA1 else 'h', c))
    return [p for p in res + [out] if p]


def seed():
    t = {'ha0': '　', 'ka0': '　'}
    for i, ch in enumerate(HALF):
        if i >= 5 and ch not in '゛゜':
            t['h%02x' % (0xA1 + i)] = ch
    for i, ch in enumerate('がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ'):  # 0x61.. (the vote confirmed all but 4)
        t['h%02x' % (0x61 + i)] = ch
    for key, ch in list(t.items()):  # katakana mode = same code, katakana glyph
        if ch != '　' and ch != 'ー':
            t['k' + key[1:]] = chr(ord(ch) + 0x60)
    t['kb0'] = 'ー'
    return t


def known(key, table):
    if key in table:
        return table[key]
    if len(key) == 4:
        try:
            return bytes.fromhex(key).decode('cp932')
        except UnicodeDecodeError:
            return None
    return None


def main(blocks_path, ds_path, table_path, match_path, *_):
    blocks = json.load(open(blocks_path))
    ds = json.load(open(ds_path))
    by_len = collections.defaultdict(dict)  # glyph count -> text -> [ids]
    for e in ds:  # a DS line can hold several messages separated by {0000}; '＠' is DS-only pause padding
        for n, seg in enumerate(e['jp'].split('{0000}')):
            t = re.sub(r'\{[0-9A-Fa-f]{4}\}|\n|＠', '', seg)
            if t:
                by_len[len(t)].setdefault(t, []).append('%s@%d' % (e['id'], n))
    msgs = []  # (block sector, group, "message.page", glyph keys)
    for b in blocks:
        words = [bytes.fromhex(w) for g in b['groups'] if g['kind'] == 'dict' for w in g['msgs']]
        for gi, g in enumerate(b['groups']):
            if g['kind'] == 'lz':
                for k, h in enumerate(g['msgs']):
                    for n, gl in enumerate(pages(expand(bytes.fromhex(h), words))):
                        msgs.append((b['sector'], gi, '%d.%d' % (k, n), gl))
    table = seed()
    while True:
        votes = collections.defaultdict(collections.Counter)
        match = {}
        voted = set()  # the shared system groups repeat in every block: one vote per distinct message
        for sec, gi, k, gl in msgs:
            kn = [known(x, table) for x in gl]
            n = sum(1 for x in kn if x)
            if n < len(gl) and n < max(3, len(gl) / 2):  # short or mostly unknown: any DS line of that length fits
                continue
            fit = [t for t in by_len.get(len(gl), ()) if all(a is None or a == c for a, c in zip(kn, t))]
            if len(fit) == 1:
                match['%d/%d/%s' % (sec, gi, k)] = by_len[len(gl)][fit[0]]
                if tuple(gl) in voted:
                    continue
                voted.add(tuple(gl))
                for key, a, c in zip(gl, kn, fit[0]):
                    if a is None:
                        votes[key][c] += 1
        new = {key: v.most_common(1)[0][0] for key, v in votes.items()
               if v.most_common(1)[0][1] >= 2 and v.most_common(1)[0][1] >= 0.8 * sum(v.values())}
        print(len(match), 'of', len(msgs), 'matched;', len(new), 'new glyphs;',
              sum(1 for v in votes.values() if len(v) > 1), 'contested')
        if not new:
            break
        table.update(new)
    json.dump(dict(sorted(table.items())), open(table_path, 'w'), ensure_ascii=False, indent=0)
    json.dump(match, open(match_path, 'w'), indent=0)
    for key, v in sorted(votes.items()):
        print('unresolved', key, dict(v.most_common(4)))
    if '--why' in sys.argv:  # which matches taught a glyph: align.py ... --why h24
        key = sys.argv[sys.argv.index('--why') + 1]
        for sec, gi, k, gl in msgs:
            ids = match.get('%d/%d/%s' % (sec, gi, k))
            if ids and key in gl:
                print(sec, gi, k, ids[0], ''.join(known(x, table) or '?' for x in gl)[:60])


if __name__ == '__main__':
    main(*sys.argv[1:])
