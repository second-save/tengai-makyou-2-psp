#!/usr/bin/env python3
"""Insert the English script into a built data track (after build.py --all-ascii).

  insert.py ORIG.iso SYSCARD.PCE BUILT.iso BLOCKS.json SCRIPT.json [--marker]     (about a minute)
      rewrites BUILT.iso in place, appends to BUILT.iso.writes, details in BUILT.iso.insert.log

A message is replaced when every page has English. Per page the original's leading control codes and its trailing
wait / newline are kept, the DS tags are dropped, placeholders (01 choice, 19 n, 1A, 1B x, 1E) are taken from the
original in order, and the text is wrapped by pixel width (LINE px, PAGE lines, then a wait).
Each block's LZ streams are re-packed into the space the old streams used plus the FF padding after them, and the
group table is repointed. The dictionary (group 1) is replaced by the 128 English strings that save the most, coded as
one byte 0x80-0xFF; the groups of hiragana readings reuse the stream of the names they read; a message without English
keeps its control codes and shows `?` for every glyph. Every rewritten block is re-extracted and compared. --marker: `[sector/group/index]` + text.
"""
import collections, json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, extract, lz

LINE, PAGE = 216, 3     # dialogue window: usable px per line, lines per page
ARG = {0x02, 0x03, 0x10, 0x11, 0x14, 0x15}   # control codes followed by an ASCII decimal argument
HOLD = {0x01: '01', 0x19: '19', 0x1A: '1A', 0x1B: '1B', 0x1E: '1E'}   # placeholders: they stay inside the text
HOLD_PX = {'01': 0, '19': 48, '1A': 48, '1B': 24, '1E': 40}   # shortcut: guessed widths of the inserted values, measure them at the width gate
EN = re.compile(r'\{([0-9A-F]{4})\}|￥Ｚ([０-９0-9])|(￥Ｓ)|(￥Ｄ)(?:￥右)?|(￥／)|￥.|(.)', re.S)
SUBST = {'☆': '*', '△': '^', '▽': 'v', 'é': 'e', '’': "'", '“': '"', '”': '"', '—': '-', '～': '~', '･': '.', '・': '.'}
MIRROR = 0x8000000
KEEP_FF = 16            # padding left after the last stream (the extractor ends the last stream there)


def tokens(m):
    """[(code or None for a glyph, bytes)] of an expanded message."""
    out, i = [], 0
    while i < len(m):
        c, j = m[i], i + 1
        if c in ARG or c == 0x19:
            while j < len(m) and 0x30 <= m[j] <= 0x39:
                j += 1
        elif 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEA or c == 0x1B and m[j:j + 1] < b' ':
            j += 1   # SJIS pair; 1B (number) keeps the cursor code that follows it (1B 08), it has no argument of its own
        out.append((c if c < 0x20 else None, m[i:j]))
        i = j
    return out


def segments(m):
    """Split at the wait code 12 (kept at the end of its segment). Same pages as align.pages: only segments with glyphs count."""
    segs, cur = [], []
    for t in tokens(m):
        cur.append(t)
        if t[0] == 0x12:
            segs.append(cur)
            cur = []
    return segs + ([cur] if cur else [])


def english(seg, en, w, problems):
    """Bytes of one page: original prefix + wrapped English + original suffix."""
    a = 0
    while a < len(seg) and seg[a][0] is not None and seg[a][0] not in HOLD:
        a += 1
    b = len(seg)
    while b > a and seg[b - 1][0] in (0x12, 0x0D):
        b -= 1
    prefix = b''.join(t for c, t in seg[:a] if c not in (0x0E, 0x0F))
    suffix = b''.join(t for c, t in seg[b:])
    holds = {}
    for c, t in seg[a:b]:
        if c in HOLD:
            holds.setdefault(HOLD[c], []).append(t)
    used = {k: 0 for k in holds}

    def hold(kind, data=None):
        n = used.get(kind, 0)
        used[kind] = n + 1
        if n >= len(holds.get(kind, [])):
            problems.append('placeholder %s not in the original' % kind)
            return []
        return [(data or holds[kind][n], HOLD_PX[kind])]

    hard = '{0001}' in en or 0x16 in [c for c, t in seg[:a]]   # choices and cards keep their own line breaks
    atoms = []            # (bytes, px); b' ' and b'\r' are break points
    for tag, z, s, d, slash, ch in EN.findall(en.strip('\n')):
        if tag:
            k = {'0001': '01', '001A': '1A', '001B': '1B', '001E': '1E'}.get(tag)
            atoms += hold(k) if k else []
        elif z:
            atoms += hold('19', b'\x19' + unicodedata.normalize('NFKC', z).encode())
        elif s:
            atoms += hold('1A')
        elif d:
            atoms += hold('1B')
        elif slash or ch == '\n' and not hard:
            if atoms and atoms[-1][0] != b' ':
                atoms.append((b' ', w[0] & 15))
        elif ch == '\n':
            atoms.append((b'\r', 0))
        elif ch:
            for x in unicodedata.normalize('NFKC', SUBST.get(ch, ch)):
                x = SUBST.get(x, x)
                if not ' ' <= x <= '~':
                    problems.append('no glyph for %r' % x)
                    x = '?'
                atoms.append((x.encode(), w[ord(x) - 0x20] & 15))
    for k in holds:
        if used[k] < len(holds[k]):
            problems.append('placeholder %s missing in the English' % k)
    lines, line, px, word, wpx = [], [], 0, [], 0
    for t, n in atoms + [(b'\r', 0)]:
        if t in (b' ', b'\r'):
            if px + wpx > LINE and line and not hard:
                while line and line[-1] == b' ':
                    line.pop()
                lines.append(line)
                line, px = [], 0
            line += word
            px += wpx
            word, wpx = [], 0
            if t == b'\r':
                lines.append(line)
                line, px = [], 0
            elif line or hard:
                line.append(t)
                px += n
            if px > LINE:
                problems.append('line wider than %d px' % LINE)
        else:
            word.append(t)
            wpx += n
    out = bytearray(prefix)
    for i, l in enumerate(lines):
        if i:
            out += b'\x12\r' if i % PAGE == 0 and b'\x12' in suffix and not hard else b'\r'
        out += b''.join(l).rstrip(b' ') if not hard else b''.join(l)
    return bytes(out) + suffix


def translate(entry, words, w, marker, log):
    """New bytes of a script entry, or None to leave it as it is."""
    if not all(p['en'] and p['en'].strip() for p in entry['pages']):   # blank lines (window erasers) stay as they are
        return None
    segs = segments(extract.expand(bytes.fromhex(entry['hex']), words))
    paged = [any(c is None for c, t in s) for s in segs]
    if sum(paged) != len(entry['pages']):
        log.append('%s: %d pages in the script, %d in the message: left as is' % (entry['at'], len(entry['pages']), sum(paged)))
        return None
    out, pages = bytearray(), iter(entry['pages'])
    for n, (seg, has) in enumerate(zip(segs, paged)):
        if not has:
            out += b''.join(t for c, t in seg)
            continue
        problems = []
        en = next(pages)['en']
        out += english(seg, '[%s] %s' % (entry['at'], en) if marker and not n else en, w, problems)
        log += ['%s page %d: %s' % (entry['at'], n, p) for p in problems]
    return bytes(out)


READING = {5: 2, 6: 3, 7: 4, 9: 8}   # groups of hiragana readings -> the names they read: one English name serves both
CODES = 128             # bytes 0x80-0xFF = dictionary word 1-128 (hook in src/vwf.s)


def runs(m):
    """Split message bytes into text runs (printable ASCII outside control-code arguments) and everything else."""
    out = []
    for c, t in tokens(m):
        text = c is None and len(t) == 1 and t[0] < 0x7F
        if out and out[-1][0] and text:
            out[-1][1] += t
        else:
            out.append([text, bytearray(t)])
    return out


def dictionary(texts, n):
    """n strings whose replacement by a 1-byte code saves the most over `texts`, greedy."""
    corpus = '\0'.join(texts)
    cnt = collections.Counter(corpus[i:i + k] for k in range(2, 11) for i in range(len(corpus) - k + 1))
    cand = {c: v for c, v in cnt.items() if v > 20 and '\0' not in c}
    words = []
    while len(words) < n and cand:
        best = max(cand, key=lambda c: ((len(c) - 1) * cand[c], c))
        words.append(best)
        del cand[best]
        corpus = corpus.replace(best, '\0')
        pairs = {best[i:i + 2] for i in range(len(best) - 1)}
        for c in cand:   # recount what the removal can have changed
            if any(c[i:i + 2] in pairs for i in range(len(c) - 1)):
                cand[c] = corpus.count(c)
    return [x.encode() for x in words]


def blank(m):
    """An untranslated message: control codes kept, `?` per glyph (bytes from 0x80 up are dictionary codes now)."""
    return b''.join(t if c is not None else b' ' if t in (b'\xa0', b'\x81\x40') else b'?' for c, t in tokens(m))


def rebuild(orig, new, b, words, log, cache):
    """Re-pack one block's streams into `new`. Returns (translated, total) messages, or None when it does not fit."""
    base, groups = b['sector'] * 2048, b['groups']
    old = [bytes.fromhex(x) for x in groups[1]['msgs']]

    def source(i):
        """Hex messages group i is built from: a reading group takes the names it reads."""
        j = READING.get(i, i)
        return groups[j if len(groups[j]['msgs']) == len(groups[i]['msgs']) else i]['msgs']

    def content(i):
        return [cache[h] if cache.get(h) is not None else blank(extract.expand(bytes.fromhex(h), old)) for h in source(i)]

    streams = {}          # old offset -> group index (groups can share a stream: the longest list wins)
    for i, g in enumerate(groups):
        if g['kind'] == 'lz' and len(g['msgs']) > (len(groups[streams[g['offset']]]['msgs']) if g['offset'] in streams else 0):
            streams[g['offset']] = i
    done = total = 0
    free, packed = [], {}
    for off, i in sorted(streams.items()):
        _, end = lz.unpack(orig, base + off, stop=lambda x, n=len(groups[i]['msgs']): x.count(0) >= n)
        assert not free or free[-1][1] <= off, 'streams overlap in block %d' % b['sector']
        free.append([off, end - base])
        total += len(source(i))
        done += sum(cache.get(h) is not None for h in source(i))
        data = b''.join(m + b'\0' for m in content(i))
        if data not in cache:
            cache[data] = lz.pack(data)
        packed[off] = cache[data]
    d = groups[1]['offset']
    free.append([d, d + sum(len(x) + 1 for x in old)])
    free.sort()
    lo, ends = free[0][0], {f[1] for f in free}
    # FF padding after the first stream (alignment gaps between the module's sections), group offsets are 16-bit
    for m in re.finditer(rb'\xff{64,}', orig[base + lo:base + 0x10000]):
        s, e = lo + m.start(), lo + m.end()
        if not any(f[0] < e and s < f[1] for f in free):
            free.append([s if s in ends else s + KEEP_FF, e - KEEP_FF])
    free.sort()
    for f, nxt in zip(free, free[1:]):   # merge adjacent runs
        if f[1] == nxt[0]:
            nxt[0], f[1] = f[0], f[0]
    was = [tuple(f) for f in free]
    for s, e in free:
        new[base + s:base + e] = b'\xff' * (e - s)
    table = b''.join(x + b'\0' for x in words)
    place, where = {}, {}
    for data in sorted(set(packed.values()), key=lambda x: (-len(x), x)):   # equal streams are stored once
        lead = b'' if where else table   # the dictionary sits right before a stream: the extractor ends it there
        f = next((f for f in free if f[1] - f[0] >= len(lead) + len(data)), None)
        if f is None:
            new[base:base + 0x10000] = orig[base:base + 0x10000]
            log.append('block %d: streams need %d bytes, %d free: left in Japanese' % (
                b['sector'], len(table) + sum(len(x) for x in set(packed.values())), sum(e - s for s, e in was)))
            return None
        new[base + f[0]:base + f[0] + len(lead) + len(data)] = lead + data
        if lead:
            place[d] = f[0]
        where[data] = f[0] + len(lead)
        f[0] += len(lead) + len(data)
    for off, data in packed.items():
        place[off] = where[data]
    for i, g in enumerate(groups):
        if g['kind'] == 'lz' and not g['msgs'] and any(s <= g['offset'] <= e for s, e in was):
            place[g['offset']] = max(f[0] for f in free)   # empty group parked at the end of a stream: keep it on padding
        if g['offset'] in place:
            p = base + b['table'] + i * 2
            assert new[p] | new[p + 1] << 8 == g['offset']
            new[p:p + 2] = place[g['offset']].to_bytes(2, 'little')
    got = extract.block(new, base, valid=lambda m: True)   # self-check: the extractor must read back what was meant
    assert got['groups'][1]['msgs'] == [x.hex() for x in words], 'block %d: dictionary read-back differs' % b['sector']
    for i, g in enumerate(got['groups']):
        if groups[i]['kind'] == 'lz' and groups[i]['msgs']:
            want = [m.hex() for m in content(i)]
            assert g['msgs'][:len(want)] == want, 'block %d group %d: read-back differs' % (b['sector'], i)
    return done, total


def main(orig_path, syscard, built, blocks_path, script_path, marker=False):
    orig = open(orig_path, 'rb').read()
    new = bytearray(open(built, 'rb').read())
    w = build.widths(orig, open(syscard, 'rb').read())
    blocks = json.load(open(blocks_path))
    old = [bytes.fromhex(x) for x in blocks[0]['groups'][1]['msgs']]   # the same dictionary in every block
    log, writes, cache = [], [], {}
    for e in json.load(open(script_path, encoding='utf-8')):
        cache[e['hex']] = translate(e, old, w, marker, log)
    words = dictionary([t.decode() for m in cache.values() if m for text, t in runs(m) if text], CODES)
    code = {x: bytes([0x80 + i]) for i, x in enumerate(words)}
    pat = re.compile(b'|'.join(re.escape(x) for x in sorted(words, key=len, reverse=True)))
    for h, m in cache.items():
        if m:
            cache[h] = b''.join(pat.sub(lambda x: code[x.group()], bytes(t)) if text else bytes(t) for text, t in runs(m))
            assert all(c < 0x80 for c in m) and b''.join(words[c - 0x80] if c >= 0x80 else bytes([c]) for c in cache[h]) == m, h
    done = total = kept = 0
    for b in blocks:
        r = rebuild(orig, new, b, words, log, cache)
        if r is None:
            kept += 1
            continue
        done, total = done + r[0], total + r[1]
        base = b['sector'] * 2048
        diff = [i for i in range(base, base + 0x10000) if new[i] != orig[i]]
        if diff:
            lo, hi = diff[0], diff[-1] + 1
            for o in (lo, lo + MIRROR):
                if o == lo or orig[o:o + hi - lo] == orig[lo:hi]:
                    new[o:o + hi - lo] = new[lo:hi]
                    writes.append('%x %s %s block %d text' % (o, orig[lo:hi].hex(), new[lo:hi].hex(), b['sector']))
    open(built, 'wb').write(new)
    open(built + '.writes', 'a').write('\n'.join(writes) + '\n')
    open(built + '.insert.log', 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('%d of %d messages in English, %d blocks left in Japanese (no room), %d log lines' % (done, total, kept, len(log)))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a, marker='--marker' in sys.argv)
