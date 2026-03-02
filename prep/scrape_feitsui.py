#!/usr/bin/env python3
"""
Scrape feitsui.com for lyrics pages beyond the BSON range.

Crawls song IDs from the website, extracts title/singer/lyrics,
and saves results to scraped_lyrics.json in a format matching
the BSON record structure. Saves progress periodically.

The JSON records are in Traditional Chinese (scraped from /zh-hant/).
match_lyrics.py will load this file alongside lyric.bson.
"""

import json
import os
import re
import time
import requests

LYRICS_URL = 'https://www.feitsui.com/zh-hant/lyrics/{id}'
OUTPUT_FILE = 'scraped_lyrics.json'
BSON_MAX_ID = 6596
SITE_MAX_ID = 6957
CRAWL_DELAY = 0.3   # seconds between page fetches
SAVE_EVERY  = 20    # save to disk every N new pages


def extract_meta(html):
    """Extract title, singer, and labels from page HTML."""
    # <title>歌手《歌名》粵語發音 ...</title>
    m = re.search(r'<title>([^《]+)《([^》]+)》', html)
    if not m:
        return None, None, []
    singer = m.group(1).strip()
    title = m.group(2).strip()

    # Labels from the info block: 歌手 X / 標籤 Y
    labels = []
    info_m = re.search(
        r'<p[^>]*>\s*歌手\s*(.*?)\s*標籤\s*(.*?)\s*</p>', html, re.DOTALL
    )
    if info_m:
        label_text = re.sub(r'<[^>]+>', '', info_m.group(2)).strip()
        if label_text:
            labels = [l.strip() for l in re.split(r'[、,，]', label_text) if l.strip()]

    return title, singer, labels


def extract_lyrics(html):
    """Extract lyrics text (Chinese + Jyutping interleaved) from page."""
    h5_end = html.find('</h5>')
    if h5_end == -1:
        return None

    section = html[h5_end:]
    p_contents = re.findall(r'<p>(.*?)</p>', section, re.DOTALL)

    all_lines = []
    for p in p_contents:
        for line in re.split(r'<br\s*/?>', p):
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean:
                all_lines.append(clean)

    lyrics_lines = [
        line for line in all_lines
        if '翡翠粵語歌詞' not in line and 'feitsui.com' not in line
    ]

    return '\n'.join(lyrics_lines) if lyrics_lines else None


def load_existing():
    """Load previously scraped records from JSON."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
        print(f'Loaded {len(records)} existing records from {OUTPUT_FILE}')
        return records
    return []


def save_records(records):
    """Save records to JSON."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=1)


def main():
    records = load_existing()
    seen_ids = {r['_id'] for r in records}

    # Determine where to start crawling
    start_id = BSON_MAX_ID + 1
    if seen_ids:
        start_id = max(max(seen_ids) + 1, start_id)

    print(f'Crawling IDs {start_id} to {SITE_MAX_ID} ...')
    new_count = 0

    for song_id in range(start_id, SITE_MAX_ID + 1):
        if song_id in seen_ids:
            continue

        url = LYRICS_URL.format(id=song_id)
        try:
            resp = requests.get(url, timeout=15)
        except Exception as e:
            print(f'  Error fetching {song_id}: {e}')
            time.sleep(2)
            continue

        if resp.status_code == 404:
            continue
        if resp.status_code != 200:
            print(f'  ID {song_id}: HTTP {resp.status_code}')
            time.sleep(2)
            continue

        html = resp.text
        title, singer, labels = extract_meta(html)
        if not title:
            continue

        lyrics = extract_lyrics(html)
        if not lyrics:
            continue

        rec = {
            '_id': song_id,
            'url': f'https://www.feitsui.com/zh-hant/lyrics/{song_id}',
            'info': {
                '歌手': [singer],
                '標籤': labels,
            },
            'title': title,
            'label': [singer] + labels,
            'lyric': lyrics,
            'lang': 'zh-hant',
        }
        records.append(rec)
        seen_ids.add(song_id)
        new_count += 1

        print(f'  [{song_id}] {title} - {singer}  ({len(lyrics.split(chr(10)))} lines)')

        if new_count % SAVE_EVERY == 0:
            save_records(records)
            print(f'  [Saved {len(records)} records to {OUTPUT_FILE}]')

        time.sleep(CRAWL_DELAY)

    # Final save
    save_records(records)
    print(f'\nDone. {new_count} new records crawled.')
    print(f'Total records in {OUTPUT_FILE}: {len(records)}')


if __name__ == '__main__':
    main()
