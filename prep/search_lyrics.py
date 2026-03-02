#!/usr/bin/env python3
"""
Search DuckDuckGo for lyrics of songs marked 'not_found'.

For each not_found song:
  1. Search DuckDuckGo for "{title} {singer} 歌詞"
  2. Try fetching lyrics from result pages (KKBOX, Mulanci, etc.)
  3. Save to google_lyrics.json periodically

The JSON records use the same structure as scraped_lyrics.json.
Run match_lyrics.py afterwards to incorporate.
"""

import csv
import json
import os
import re
import time
import requests
from ddgs import DDGS
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
}

CSV_FILE = 'selection_1986_2025_with_lyrics.csv'
OUTPUT_FILE = 'google_lyrics.json'
SEARCH_DELAY = 3    # seconds between DuckDuckGo searches
FETCH_DELAY = 1     # seconds between page fetches
SAVE_EVERY = 10     # save progress every N successful scrapes


# ── DuckDuckGo search ─────────────────────────────────────────────────────
def ddg_search(query, num=5):
    """Search DuckDuckGo and return list of result URLs."""
    try:
        results = DDGS().text(query, max_results=num)
        return [r['href'] for r in results]
    except Exception as e:
        print(f'    [DDG error: {e}]')
        return []


# ── Lyrics extractors for different sites ──────────────────────────────────
def fetch_page(url):
    """Fetch a URL and return BeautifulSoup, or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception:
        return None


def extract_kkbox(soup):
    """Extract lyrics from KKBOX page."""
    el = soup.select_one('[class*="lyrics"]')
    if not el:
        return None
    text = el.get_text('\n').strip()
    # Remove 作詞/作曲 header lines
    lines = text.split('\n')
    lyrics_lines = []
    for line in lines:
        s = line.strip()
        if not s:
            lyrics_lines.append('')
        elif re.match(r'^(作詞|作曲|編曲|監製|製作人)\s*[：:]', s):
            continue
        else:
            lyrics_lines.append(s)
    # Strip leading/trailing blanks
    while lyrics_lines and not lyrics_lines[0]:
        lyrics_lines.pop(0)
    while lyrics_lines and not lyrics_lines[-1]:
        lyrics_lines.pop()
    return '\n'.join(lyrics_lines) if lyrics_lines else None


def extract_mulanci(soup):
    """Extract lyrics from Mulanci page."""
    el = soup.select_one('div.lyrics')
    if el:
        text = el.get_text('\n').strip()
        if len(text) > 30:
            return _clean_lyrics(text)
    for sel in ['.lyric-text', '#lyrics', 'pre']:
        el = soup.select_one(sel)
        if el:
            text = el.get_text('\n').strip()
            if len(text) > 30:
                return _clean_lyrics(text)
    return None


def extract_mojim(soup):
    """Extract lyrics from Mojim page."""
    el = soup.select_one('#fsZx1')
    if not el:
        el = soup.select_one('.fsZx1')
    if el:
        text = el.get_text('\n').strip()
        return _clean_lyrics(text) if len(text) > 30 else None
    return _find_largest_chinese_block(soup)


def extract_generic(soup):
    """Generic lyrics extraction: find the largest Chinese text block."""
    return _find_largest_chinese_block(soup)


def extract_appleofmyeye(soup):
    """Extract lyrics from appleofmyeye.com.tw."""
    # Usually in a <td> or <div> with the lyrics
    return _find_largest_chinese_block(soup)


def _find_largest_chinese_block(soup):
    """Find the largest block of Chinese text in the page."""
    best = None
    best_score = 0
    for el in soup.find_all(['div', 'pre', 'p', 'td', 'section']):
        text = el.get_text('\n').strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # Good lyrics: mainly Chinese, many lines, short lines, not too long
        if chinese_count > 30 and 5 < len(lines) < 200:
            avg_len = sum(len(l) for l in lines) / len(lines)
            if avg_len < 40:
                # Penalise very large blocks (probably the whole page)
                score = chinese_count - max(0, len(lines) - 80) * 5
                if score > best_score:
                    best_score = score
                    best = text
    if best:
        return _clean_lyrics(best)
    return None


def _clean_lyrics(text):
    """Clean up extracted lyrics text."""
    lines = text.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        # Skip metadata lines
        if re.match(r'^(作詞|作曲|編曲|監製|製作人|詞|曲|Lyrics|Music|Composer)\s*[：:]', s):
            continue
        if re.match(r'^(歌手|演唱|原唱|翻唱)\s*[：:]', s):
            continue
        clean.append(s)
    # Strip leading/trailing blanks
    while clean and not clean[0]:
        clean.pop(0)
    while clean and not clean[-1]:
        clean.pop()
    return '\n'.join(clean) if clean else None


# Site-specific extractors, ordered by preference
EXTRACTORS = [
    ('kkbox.com', extract_kkbox),
    ('mojim.com', extract_mojim),
    ('mulanci.org', extract_mulanci),
    ('appleofmyeye.com', extract_appleofmyeye),
]


def try_extract_lyrics(urls):
    """Try to extract lyrics from a list of URLs. Returns lyrics text or None."""
    # First pass: try preferred sites
    for url in urls:
        for domain, extractor in EXTRACTORS:
            if domain in url:
                soup = fetch_page(url)
                if soup:
                    lyrics = extractor(soup)
                    if lyrics and len(lyrics) > 30:
                        return lyrics, url
                time.sleep(FETCH_DELAY)
                break

    # Second pass: try any remaining non-video URLs with generic extractor
    for url in urls:
        if any(skip in url for skip in ['youtube.com', 'youtu.be', 'facebook.com', 'instagram.com']):
            continue
        if any(domain in url for domain, _ in EXTRACTORS):
            continue  # already tried
        soup = fetch_page(url)
        if soup:
            lyrics = extract_generic(soup)
            if lyrics and len(lyrics) > 30:
                return lyrics, url
        time.sleep(FETCH_DELAY)

    return None, None


# ── Main ───────────────────────────────────────────────────────────────────
def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_records(records):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=1)


def main():
    # Load target songs
    with open(CSV_FILE, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    targets = []
    for row in rows:
        if row['Status'] == 'not_found':
            targets.append(row)

    print(f'Found {len(targets)} not_found songs to search')

    # Load existing results (for resume)
    records = load_existing()
    done_keys = {(r['title'], r['info']['歌手'][0]) for r in records}
    print(f'Already scraped: {len(done_keys)}')

    new_count = 0
    failed = 0
    rec_id = max((r.get('_id', 0) for r in records), default=10000)

    for i, row in enumerate(targets, 1):
        title = row['Title'].strip()
        singer = row['Singer'].strip()

        # Skip already done
        if (title, singer) in done_keys:
            continue

        print(f'[{i}/{len(targets)}] {title} - {singer} ({row["Year"]})')

        # Search
        query = f'{title} {singer} 歌詞'
        urls = ddg_search(query)

        if not urls:
            print(f'    -> No search results')
            failed += 1
            time.sleep(SEARCH_DELAY)
            continue

        print(f'    -> {len(urls)} results, trying extraction...')

        # Try to extract lyrics
        lyrics, source_url = try_extract_lyrics(urls)

        if lyrics is None:
            print(f'    -> Could not extract lyrics')
            failed += 1
            time.sleep(SEARCH_DELAY)
            continue

        line_count = len(lyrics.split('\n'))
        print(f'    -> Got {line_count} lines from {source_url[:60]}')

        rec_id += 1
        rec = {
            '_id': rec_id,
            'url': source_url,
            'info': {
                '歌手': [singer],
                '標籤': [],
            },
            'title': title,
            'label': [singer],
            'lyric': lyrics,
            'lang': 'zh-hant',
            'source': 'google',
        }
        records.append(rec)
        done_keys.add((title, singer))
        new_count += 1

        if new_count % SAVE_EVERY == 0:
            save_records(records)
            print(f'    [Saved {len(records)} records]')

        time.sleep(SEARCH_DELAY)

    # Final save
    save_records(records)

    print(f'\n{"="*60}')
    print(f'New lyrics found: {new_count}')
    print(f'Failed: {failed}')
    print(f'Total in {OUTPUT_FILE}: {len(records)}')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
