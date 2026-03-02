#!/usr/bin/env python3
"""
Match songs from selection_1986_2025.csv against lyric.bson.
BSON is in Simplified Chinese; titles/singers are converted to Traditional
via OpenCC, then character-variant-normalized for matching.

Output: selection_1986_2025_with_lyrics.csv
  Columns: Title, Singer, Year, Lyrics, Status
  Status is "matched" or "not_found"
"""

import csv
import json
import os
import re
import bson
from opencc import OpenCC

s2t = OpenCC('s2t')

# ── Character-variant normalisation table ──────────────────────────────────
# Many Traditional Chinese characters have accepted variant forms.
# We normalise both CSV titles and BSON (after s2t) to a single canonical
# form so that e.g. 陪著你走 == 陪着你走.
#
#   FROM  TO    Example
#   妳    你    真的愛妳 → 真的愛你
#   祇    只    祇想一生跟你走
#   豔    艷
#   著    着    陪著你走 → 陪着你走
#   闋    闕    千千闋歌 → 千千闕歌
#   燄    焰    烈燄 → 烈焰
#   唇    脣    紅唇 → 紅脣
#   嫻    嫺    陳慧嫻 → 陳慧嫺
#   裏    裡    夢裏 → 夢裡
#   嘆    歎
_NORM = str.maketrans(
    '\u59b3\u7947\u8c54\u8457\u95cb\u71c4\u5507\u5afb\u88cf\u5606痴',
    '\u4f60\u53ea\u8277\u7740\u95d5\u7130\u8123\u5afa\u88e1\u6b4e癡',
)

def _nc(text):
    """Normalise variant Traditional Chinese characters."""
    return text.translate(_NORM)

def norm_title(text):
    """Strip, normalise chars, drop punctuation/spaces, lowercase."""
    text = _nc(text.strip())
    text = re.sub(r'[^\w]', '', text, flags=re.UNICODE)
    return text.lower()

def norm_singer(text):
    """Strip, normalise chars, drop whitespace, lowercase."""
    text = _nc(text.strip())
    text = re.sub(r'\s+', '', text)
    return text.lower()

def split_singers(s):
    """Split a CSV singer field on common Cantonese delimiters."""
    return [x.strip() for x in re.split(r'[、／/&,，]', s) if x.strip()]

def singers_overlap(a_list, b_list):
    """True if any singer in a_list matches any in b_list (exact or substring)."""
    for a in a_list:
        for b in b_list:
            if a == b:
                return True
            if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
                return True
    return False

# ── Load BSON ──────────────────────────────────────────────────────────────
print('Loading BSON ...')
with open('lyric.bson', 'rb') as f:
    records = bson.decode_all(f.read())
print(f'  {len(records)} BSON records loaded.')

# Index: norm_title -> list of (norm_singers, record, source)
#   source = 'bson' or 'json' or 'google'
idx = {}
for rec in records:
    t = s2t.convert(rec.get('title', '')).strip()
    nt = norm_title(t)

    info = rec.get('info', {})
    singers_raw = info.get('\u6b4c\u624b', [])          # 歌手
    labels_raw  = rec.get('label', [])

    all_singers = list({s2t.convert(s).strip()
                        for s in singers_raw + labels_raw if s.strip()})
    ns = [norm_singer(s) for s in all_singers]

    idx.setdefault(nt, []).append((ns, rec, 'bson'))

# ── Load scraped JSON (if present) ─────────────────────────────────────────
SCRAPED_FILE = 'scraped_lyrics.json'
if os.path.exists(SCRAPED_FILE):
    with open(SCRAPED_FILE, 'r', encoding='utf-8') as f:
        scraped_records = json.load(f)
    print(f'  {len(scraped_records)} scraped JSON records loaded.')

    for rec in scraped_records:
        is_trad = rec.get('lang') == 'zh-hant'
        t = rec.get('title', '').strip()
        if not is_trad:
            t = s2t.convert(t)
        nt = norm_title(t)

        info = rec.get('info', {})
        singers_raw = info.get('歌手', info.get('\u6b4c\u624b', []))
        labels_raw  = rec.get('label', [])

        all_singers = list({(s.strip() if is_trad else s2t.convert(s).strip())
                            for s in singers_raw + labels_raw if s.strip()})
        ns = [norm_singer(s) for s in all_singers]

        idx.setdefault(nt, []).append((ns, rec, 'json'))
else:
    print(f'  (No {SCRAPED_FILE} found, skipping.)')

# ── Load Google-searched lyrics JSON (if present) ──────────────────────────
GOOGLE_FILE = 'google_lyrics.json'
if os.path.exists(GOOGLE_FILE):
    with open(GOOGLE_FILE, 'r', encoding='utf-8') as f:
        google_records = json.load(f)
    print(f'  {len(google_records)} Google-searched records loaded.')

    for rec in google_records:
        is_trad = rec.get('lang') == 'zh-hant'
        t = rec.get('title', '').strip()
        if not is_trad:
            t = s2t.convert(t)
        nt = norm_title(t)

        info = rec.get('info', {})
        singers_raw = info.get('歌手', info.get('\u6b4c\u624b', []))
        labels_raw  = rec.get('label', [])

        all_singers = list({(s.strip() if is_trad else s2t.convert(s).strip())
                            for s in singers_raw + labels_raw if s.strip()})
        ns = [norm_singer(s) for s in all_singers]

        idx.setdefault(nt, []).append((ns, rec, 'google'))
else:
    print(f'  (No {GOOGLE_FILE} found, skipping.)')

print(f'  {len(idx)} unique normalised titles indexed.')

# ── Lyricist extraction ────────────────────────────────────────────────────
_LYRICIST_RE = re.compile(
    r'^(?:作詞|填詞|詞|Lyricist|lyricist)\s*[：:.]\s*(.+)',
    re.MULTILINE,
)

def extract_lyricist(rec, source):
    """Return lyricist string from record metadata or lyrics text."""
    info = rec.get('info', {})
    is_trad = rec.get('lang') == 'zh-hant'

    # 1) Try info['标签'] (BSON) or info['標籤'] (scraped/google)
    tags = info.get('标签', info.get('標籤', []))
    if tags:
        lyricist = tags[0] if isinstance(tags, list) else tags
        if not is_trad:
            lyricist = s2t.convert(lyricist)
        return lyricist.strip()

    # 2) Parse first lines of lyrics text
    lyric = rec.get('lyric', '')
    m = _LYRICIST_RE.search(lyric[:500])
    if m:
        val = m.group(1).strip()
        if not is_trad:
            val = s2t.convert(val)
        return val

    return ''

# ── Matching logic ─────────────────────────────────────────────────────────
def find(title, singers):
    """Return (record, source, match_type) or (None, None, None).
    match_type: 'singer' if singer matched, 'title_only' if fallback."""
    ncs = [norm_singer(s) for s in singers]
    for t_key in _title_variants(title):
        if t_key not in idx:
            continue
        cands = idx[t_key]
        # prefer singer-matched
        for ns, rec, src in cands:
            if singers_overlap(ncs, ns):
                return rec, src, 'singer'
        # fallback: unique title
        if len(cands) == 1:
            return cands[0][1], cands[0][2], 'title_only'
    return None, None, None

def _title_variants(title):
    """Yield normalised title keys to try (original, without parenthetical)."""
    nt = norm_title(title)
    yield nt
    stripped = re.sub(r'[\(\uff08].*?[\)\uff09]', '', title).strip()
    ns = norm_title(stripped)
    if ns != nt:
        yield ns

# ── Process CSV ────────────────────────────────────────────────────────────
print('\nMatching CSV entries ...')
with open('selection_1986_2025.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

matched = scraped = googled = not_found = 0
title_only_warnings = []
results = []

for row in rows:
    title   = row['Title'].strip()
    singers = split_singers(row['Singer'])
    year    = row['Year']

    rec, src, match_type = find(title, singers)
    if rec:
        is_trad = rec.get('lang') == 'zh-hant'
        lyrics = rec.get('lyric', '')
        if not is_trad:
            lyrics = s2t.convert(lyrics)
        lyricist = extract_lyricist(rec, src)
        if src == 'google':
            googled += 1
            status = 'google'
        elif src == 'json':
            scraped += 1
            status = 'scraped'
        else:
            matched += 1
            status = 'matched'
        # Track BSON title-only matches for manual review
        if src == 'bson' and match_type == 'title_only':
            # Get the BSON record's singers for display
            info = rec.get('info', {})
            bson_singers = info.get('\u6b4c\u624b', info.get('歌手', []))
            bson_singers_str = ', '.join(s2t.convert(s) if not is_trad else s
                                         for s in bson_singers)
            title_only_warnings.append(
                f'  {year} | {row["Singer"]} \u2013 {title}  '
                f'(BSON has: {bson_singers_str})')
        results.append(dict(Title=row['Title'], Singer=row['Singer'],
                            Year=year, Lyricist=lyricist,
                            Lyrics=lyrics, Status=status))
    else:
        not_found += 1
        results.append(dict(Title=row['Title'], Singer=row['Singer'],
                            Year=year, Lyricist='',
                            Lyrics='', Status='not_found'))

print(f'\n  Matched (BSON):    {matched}')
print(f'  Scraped (JSON):    {scraped}')
print(f'  Google:            {googled}')
print(f'  Not found:         {not_found}')
print(f'  Total:             {len(results)}')

if title_only_warnings:
    print(f"\n{'='*60}")
    print(f'BSON title-only matches (singer mismatch) [{len(title_only_warnings)}]:')
    print(f"{'='*60}")
    for w in title_only_warnings:
        print(w)

# ── Write output ───────────────────────────────────────────────────────────
out = 'selection_1986_2025_with_lyrics.csv'
with open(out, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['Title','Singer','Year','Lyricist','Lyrics','Status'])
    w.writeheader()
    w.writerows(results)
print(f'\nSaved to {out}')

# ── List not-found ─────────────────────────────────────────────────────────
if not_found:
    print(f"\n{'='*60}")
    print(f'Songs NOT FOUND ({not_found}):')
    print(f"{'='*60}")
    for r in results:
        if r['Status'] == 'not_found':
            print(f"  {r['Year']} | {r['Singer']} \u2013 {r['Title']}")
