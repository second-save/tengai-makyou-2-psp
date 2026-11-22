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
PAD_MARGIN = 64         # enemy records: bytes of sector padding left after the data it pads


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
    out = bytearray(prefix + (b' ' if en.startswith(' ') and not hard else b''))   # fragments printed after a name keep their space
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
    top = b.get('end', 0x10000)   # FF padding past this belongs to other data
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
    for m in re.finditer(rb'\xff{64,}', orig[base + lo:base + top]):
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
            new[base:base + top] = orig[base:base + top]
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
    got = extract.block(new, base, valid=lambda m: True, tab=b['table'])   # self-check: the extractor must read back what was meant
    assert got['groups'][1]['msgs'] == [x.hex() for x in words], 'block %d: dictionary read-back differs' % b['sector']
    for i, g in enumerate(got['groups']):
        if groups[i]['kind'] == 'lz' and groups[i]['msgs']:
            want = [m.hex() for m in content(i)]
            assert g['msgs'][:len(want)] == want, 'block %d group %d: read-back differs' % (b['sector'], i)
    return done, total


def enemy_english(m, en, log, at):
    """Plain ASCII for an enemy name or line (copied by 71:$752A: `$0`-`$3` = name, `$n` = newline), or None."""
    out = ''
    for tag, z, s, d, slash, ch in EN.findall(en.strip()):
        if z:
            out += '$%d' % (int(unicodedata.normalize('NFKC', z)) - 1)
        elif slash or ch == '\n':
            out += '$n'
        elif ch:
            x = unicodedata.normalize('NFKC', SUBST.get(ch, ch))
            if not all(' ' <= c <= '~' and c != '$' for c in x):
                log.append('%s: no glyph for %r' % (at, x))
                return None
            out += x
        elif tag or s or d:
            log.append('%s: control tag in an enemy string' % at)
            return None
    if sorted(re.findall(rb'\$[0-3]', m)) != sorted(re.findall(rb'\$[0-3]', out.encode())):
        log.append('%s: name placeholders differ' % at)
        return None
    return out.encode()


def enemies(orig, new, script, back, log, writes):
    """Rewrite every area's enemy records in English. The records go where the old ones were, then into the FF run before
    the battle stream; the enemy pointers move with them. An area that does not fit stays in Japanese."""
    text = {bytes.fromhex(e['hex']): (e['pages'][0]['en'], e['at']) for e in script
            if len(e['pages']) == 1 and e['pages'][0]['en']}   # an enemy name can also be a module message
    cache, done = {}, 0
    areas = extract.enemies(orig)
    for area in areas:
        img = bytearray(orig[area['image']:area['image'] + 0x10000])

        def english(m):
            if not m:
                return m
            if m not in cache:
                en, at = text.get(m, (None, None))
                cache[m] = en and enemy_english(m, en, log, at)
            return cache[m] or m
        run = re.search(rb'\xff+$', img[:0xF400 - back])   # FF run ending at the battle stream
        rooms = [[area['start'], area['end']]] + ([[run.start() + KEEP_FF, run.end()]] if run else [])
        # then the padding that ends a data blob on a sector boundary (00 or FF up to a multiple of 0x800), after a margin
        # shortcut: assumed unread (nothing seen pointing into it), verified in one area only
        rooms += [[m.start() + PAD_MARGIN, m.end()] for m in re.finditer(rb'\x00{192,}|\xff{192,}', img[:0xF000])
                  if m.end() % 0x800 == 0]
        rooms = [x + [x[0]] for x in rooms]

        def record(r):
            return r['head'] + english(r['name']) + b'\0' + bytes([r['f670']]) + b''.join(
                bytes([k, a]) + english(m) + b'\0' for k, a, m in r['entries']) + b'\0' + r['tail']
        place, room_total = {}, sum(x[1] - x[0] for x in rooms)
        for p, r in area['records'].items():
            body = record(r)

            def start(x):   # right after the previous record, its 2-byte tail can be this record's first 2 bytes
                return x[0] - 2 if x[0] > x[2] and img[x[0] - 2:x[0]] == body[:2] else x[0]
            room = next((x for x in rooms if x[1] - start(x) >= len(body)), None)
            if room is None:
                break
            at = start(room)
            img[at:at + len(body)] = body
            place[p], room[0] = at, at + len(body)
        else:
            for x in area['ptrs']:
                img[x:x + 2] = place[orig[area['image'] + x] | orig[area['image'] + x + 1] << 8].to_bytes(2, 'little')
            got = extract.enemy_area(img, 0)['records']
            for p, r in area['records'].items():
                g = got[place[p]]
                assert (g['head'], g['name'], g['f670'], g['entries'], g['tail']) == (r['head'], english(r['name']), r['f670'], [
                    (k, a, english(m)) for k, a, m in r['entries']], r['tail']), 'enemies at %#x: read-back differs' % area['image']
            base = area['image']
            for o in (base, base + MIRROR):
                if o == base or orig[o:o + 0x10000] == orig[base:base + 0x10000]:
                    for s, e in spans(orig[base:base + 0x10000], img):
                        writes.append('%x %s %s enemy records' % (o + s, orig[o + s:o + e].hex(), img[s:e].hex()))
                        new[o + s:o + e] = img[s:e]
            done += 1
            continue
        log.append('enemies at %#x: %d bytes of records, %d of room: left in Japanese' % (
            area['image'], sum(len(record(r)) for r in area['records'].values()), room_total))
    return done, len(areas)


def spans(a, b):
    """[start, end) runs where a and b differ."""
    out = []
    for i in range(len(a)):
        if a[i] != b[i]:
            if out and out[-1][1] == i:
                out[-1][1] = i + 1
            else:
                out.append([i, i + 1])
    return out


def main(orig_path, syscard, built, blocks_path, script_path, marker=False):
    orig = open(orig_path, 'rb').read()
    new = bytearray(open(built, 'rb').read())
    w = build.widths(orig, open(syscard, 'rb').read())
    blocks = json.load(open(blocks_path))
    blocks.append(dict(extract.SYSTEXT, groups=extract.block(orig, extract.SYSTEXT['sector'] * 2048, tab=extract.SYSTEXT['table'])['groups']))
    old = [bytes.fromhex(x) for x in blocks[0]['groups'][1]['msgs']]   # the same dictionary in every block
    log, writes, cache = [], [], {}
    for e in json.load(open(script_path, encoding='utf-8')):
        if not e['at'].startswith('enemy/'):   # enemy records are plain SJIS: enemies() writes them
            cache[e['hex']] = translate(e, old, w, marker, log)
    words = dictionary([t.decode() for m in cache.values() if m for text, t in runs(m) if text], CODES)
    code = {x: bytes([0x80 + i]) for i, x in enumerate(words)}
    pat = re.compile(b'|'.join(re.escape(x) for x in sorted(words, key=len, reverse=True)))
    for h, m in cache.items():
        if m:
            # the handler of a decimal-argument code reads the byte after its digits itself, past the dictionary hook
            # (seen: 19 31 86 drew 86 as a kanji lead byte): keep that byte plain
            rs, parts = runs(m), []
            for k, (text, t) in enumerate(rs):
                keep = 1 if k and rs[k - 1][1][0] in ARG | {0x19} else 0
                parts.append(bytes(t[:keep]) + pat.sub(lambda x: code[x.group()], bytes(t[keep:])) if text else bytes(t))
            cache[h] = b''.join(parts)
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
    # battle lines: one stream, the same bytes at every copy
    msgs, copies = extract.battle(orig)
    want = [cache.get(m.hex()) or blank(m) for m in msgs]
    packed = lz.pack_best(b''.join(m + b'\0' for m in want))   # greedy was 66 bytes over the room
    assert lz.unpack(packed)[0].split(b'\0')[:len(msgs)] == want
    # the stream ends with ADPCM RAM: when it is too long it starts earlier, in the FF padding before it (56 bytes in
    # the tightest copy), and the source address in the opener (71:$7502 LDA #$F4 / LDX #$00) moves with it
    back = max(0, len(packed) - extract.BATTLE_ROOM)
    packed = packed.ljust(extract.BATTLE_ROOM, b'\0')
    code = extract.BATTLE_CODE
    patch = bytes([0xA9, (0xF400 - back) >> 8, 0xA2, (0xF400 - back) & 255])
    assert orig[code:code + 4] == b'\xa9\xf4\xa2\x00'
    for o in (code, code + MIRROR) if back else ():
        writes.append('%x %s %s battle text address' % (o, orig[o:o + 4].hex(), patch.hex()))
        new[o:o + 4] = patch
    for o in copies:
        o -= back
        assert orig[o:o + back] == b'\xff' * back, 'battle stream: %d bytes too long for the padding at %#x' % (back, o)
        writes.append('%x %s %s battle text' % (o, orig[o:o + len(packed)].hex(), packed.hex()))
        new[o:o + len(packed)] = packed
    assert extract.battle(new) == (want, [o - back for o in copies]), 'battle stream: read-back differs'
    done, total = done + sum(1 for m in msgs if cache.get(m.hex())), total + len(msgs)
    e_done, e_total = enemies(orig, new, json.load(open(script_path, encoding='utf-8')), back, log, writes)
    print('enemy records: %d of %d areas in English' % (e_done, e_total))
    open(built, 'wb').write(new)
    open(built + '.writes', 'a').write('\n'.join(writes) + '\n')
    open(built + '.insert.log', 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('%d of %d messages in English, %d blocks left in Japanese (no room), %d log lines' % (done, total, kept, len(log)))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a, marker='--marker' in sys.argv)
