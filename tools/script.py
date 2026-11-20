#!/usr/bin/env python3
"""Build the working script: one entry per distinct message, with the DS English attached page by page.

  script.py BLOCKS.json MATCH.json DS_SCRIPT.json OUT.json [DS_CATALOG.json ...]

Entry: `hex` (original bytes, the key used at insertion: the same message sits in many modules), `at` (first place seen,
sector/group/index), `uses`, `jp` (decoded with dictionary words expanded), `pages` = one item per page (pages end at the
wait code 12): `ds` (DS line id@segment, or null) and `en` (its English with the DS control tags, or null = to translate).
One-page messages without a DS line are looked up in the DS catalogs (item, enemy, battle text) by exact text: `ds` = "catalog".
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import align
from codec import Codec
from extract import expand


def norm(s):
    return re.sub(r'\{[^}]*\}|\[..\]|￥.|\s', '', s)


def records(node):
    """Every dict holding both jp and en, anywhere in a catalog file."""
    if isinstance(node, dict):
        if node.get('jp') and node.get('en'):
            yield node
        node = list(node.values())
    if isinstance(node, list):
        for x in node:
            yield from records(x)


def near(keyed, codec, ds_path, cutoff=0.9):
    """Area pages with no DS line: take the closest DS line (difflib ratio >= cutoff on the bare text; 0.85-0.9 gave
    wrong items and DS lines with extra parts; a page with codes / digits needs DS English with tags); `ds` =
    "near:<id> <ratio>" so these stay reviewable (the exact match missed them by a few characters)."""
    import difflib
    bare = lambda t: re.sub(r'\{[^}]*\}|￥.|[\s　＠｜！？!?、。…・]', '', t)
    def text(keys):
        out = []
        for k in keys:
            if len(k) == 4:
                out.append(bytes.fromhex(k).decode('shift_jis', 'replace'))
            else:
                out.append(codec.dec.get((k[0], int(k[1:], 16)), ''))
        return ''.join(out)
    lines = {}
    for e in json.load(open(ds_path, encoding='utf-8')):
        segs, jps = e['en_tagged'].split('{0000}'), e['jp_clean'].split('{0000}') if '{0000}' in e['jp_clean'] else [e['jp_clean']]
        for n, jp in enumerate(jps):
            if bare(jp):
                lines.setdefault(bare(jp), ('%s@%d' % (e['id'], n), segs[n] if len(segs) == len(jps) else e['en']))
    keys = list(lines)
    hits = 0
    for entry, pk in keyed:
        for page, k in zip(entry['pages'], pk):
            if page['en']:
                continue
            t = bare(text(k))
            m = difflib.get_close_matches(t, keys, n=1, cutoff=cutoff) if len(t) >= 4 else []
            if m and lines[m[0]][1].strip() and not (set('０１２３４５６７８９') & set(text(k)) and '{' not in lines[m[0]][1] and '￥' not in lines[m[0]][1]):
                page.update(ds='near:%s %.2f' % (lines[m[0]][0], difflib.SequenceMatcher(None, t, m[0]).ratio()), en=lines[m[0]][1])
                hits += 1
    print(hits, 'pages filled from near-miss DS lines')


def main(blocks_path, match_path, ds_path, out_path, *catalogs, iso='work/content/HCD1022_02.iso'):
    cat = {}
    for path in catalogs:
        for r in records(json.load(open(path, encoding='utf-8'))):
            cat.setdefault(norm(r['jp']), r['en'])
    blocks = json.load(open(blocks_path))
    match = json.load(open(match_path))
    en = {}
    for e in json.load(open(ds_path, encoding='utf-8')):
        segs = e['en_tagged'].split('{0000}')
        same = len(segs) == len(e['jp'].split('{0000}'))
        for n in range(len(e['jp'].split('{0000}'))):
            en['%s@%d' % (e['id'], n)] = segs[n] if same else e['en']  # 30 lines lost a separator: whole line then
    codec, out, keyed = Codec(), {}, []
    for b in blocks:
        words = [bytes.fromhex(w) for w in b['groups'][1]['msgs']]
        for gi, g in enumerate(b['groups']):
            if g['kind'] != 'lz':
                continue
            for k, h in enumerate(g['msgs']):
                if h in out:
                    out[h]['uses'] += 1
                    continue
                full = expand(bytes.fromhex(h), words)
                pages = []
                for n in range(len(align.pages(full))):
                    ids = match.get('%d/%d/%d.%d' % (b['sector'], gi, k, n))
                    pages.append({'ds': ids[0] if ids else None, 'en': en.get(ids[0]) if ids else None})
                out[h] = {'hex': h, 'at': '%d/%d/%d' % (b['sector'], gi, k), 'uses': 1, 'jp': codec.decode(full, strict=False), 'pages': pages}
                if gi >= 14:
                    keyed.append((out[h], align.pages(full)))
                if len(pages) == 1 and not pages[0]['en'] and norm(out[h]['jp']) in cat:
                    pages[0].update(ds='catalog', en=cat[norm(out[h]['jp'])])
    near(keyed, codec, ds_path)
    import extract
    for k, m in enumerate(extract.battle(open(iso, 'rb').read())[0]):   # battle lines: their own stream, one page each
        jp = codec.decode(m, strict=False)
        e = out.setdefault(m.hex(), {'hex': m.hex(), 'at': 'battle/%d' % k, 'uses': 0, 'jp': jp, 'pages': [{'ds': None, 'en': None}]})
        e['uses'] += 1
        if e['pages'] and not e['pages'][0]['en'] and norm(jp) in cat:   # an empty message has no page
            e['pages'][0].update(ds='catalog', en=cat[norm(jp)])
    # enemy names and lines (plain SJIS, $0 = name, $n = newline): matched to the DS catalogs without codes or punctuation
    bare = lambda s: re.sub(r'￥Ｚ.|\$.|￥.|[、！!｜\s]', '', s)
    ecat = {}
    for path in catalogs:
        for r in records(json.load(open(path, encoding='utf-8'))):
            ecat.setdefault(bare(r['jp']), r['en'])
    for area in extract.enemies(open(iso, 'rb').read()):
        for r in area['records'].values():
            for m in [r['name']] + [e[2] for e in r['entries'] if e[2]]:
                if m.hex() not in out:
                    jp = m.decode('shift_jis')
                    out[m.hex()] = {'hex': m.hex(), 'at': 'enemy/%d' % sum(e['at'].startswith('enemy/') for e in out.values()),
                                    'uses': 0, 'jp': jp, 'pages': [{'ds': 'catalog' if bare(jp) in ecat else None, 'en': ecat.get(bare(jp))}]}
                out[m.hex()]['uses'] += 1
    over = json.load(open(os.path.join(os.path.dirname(out_path), 'overrides.json'), encoding='utf-8'))
    for h, text in over.items():   # a string = the whole (one-page) message; a list = English per page, null = keep
        if h not in out:
            continue
        if isinstance(text, list):
            assert len(text) == len(out[h]['pages']), '%s: %d pages, %d in overrides' % (h, len(out[h]['pages']), len(text))
            for page, t in zip(out[h]['pages'], text):
                if t:
                    page.update(ds='override', en=t)
        else:
            out[h]['pages'] = [{'ds': 'override', 'en': text}]
    entries = [e for e in out.values() if e['pages']]
    json.dump(entries, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    pages = [p for e in entries for p in e['pages']]
    print(len(entries), 'messages,', len(pages), 'pages,', sum(1 for p in pages if p['en']), 'with English,',
          sum(1 for e in entries if all(p['en'] for p in e['pages'])), 'messages fully covered')


if __name__ == '__main__':
    main(*sys.argv[1:])
