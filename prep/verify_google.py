#!/usr/bin/env python3
"""
Verify google_lyrics.json: flag records where the scraped page
likely contains lyrics for a DIFFERENT song than what was searched.

Strategy:
  - Fetch the source URL again and extract the page's own song title
  - Compare to the record's title
  - If they differ, flag for manual check

Also flag: unusual sources, very long/short lyrics, etc.
"""

import json
import re
import requests
from urllib.parse import unquote
from bs4 import BeautifulSoup

with open('google_lyrics.json', 'r', encoding='utf-8') as f:
    records = json.load(f)

print(f'Total records: {len(records)}')


def extract_page_title(url):
    """Try to extract the song title that the page claims to be about."""
    # From URL patterns
    # KKBOX: title is in the page
    # Mulanci: title is in the page
    # appleofmyeye: title often in URL
    # Others: try page <title> or <h1>

    # Quick extraction from URL for known sites
    if 'kkbox.com' in url:
        return 'kkbox'  # need to fetch
    if 'mulanci.org' in url:
        return 'mulanci'
    if 'appleofmyeye.com' in url:
        return 'appleofmyeye'
    return 'other'


def normalise(s):
    """Normalise for comparison: lowercase, strip punctuation/spaces."""
    s = s.lower().strip()
    # Remove common suffixes/prefixes
    s = re.sub(r'\s*[\-–—]\s*歌詞.*', '', s)
    s = re.sub(r'\s*歌詞.*', '', s)
    s = re.sub(r'\s*lyrics.*', '', s, flags=re.IGNORECASE)
    # Remove punctuation
    s = re.sub(r'[^\w\u4e00-\u9fff]', '', s)
    return s


def title_from_kkbox_lyrics(lyric_text):
    """KKBOX lyrics often DON'T contain the title. Skip."""
    return None


def title_from_first_lines(lyric_text, expected_title):
    """Check if a different song title appears in the first few lines."""
    lines = [l.strip() for l in lyric_text.split('\n') if l.strip()]
    # Look for patterns like "Song Title - Artist" or "《Song Title》"
    for line in lines[:5]:
        m = re.search(r'《(.+?)》', line)
        if m:
            return m.group(1)
    return None


# ── Main check ─────────────────────────────────────────────────────────────
suspect = []

for rec in records:
    title = rec['title']
    singer = rec['info']['歌手'][0] if rec['info']['歌手'] else ''
    url = rec['url']
    lyric = rec['lyric']
    lines = [l.strip() for l in lyric.split('\n') if l.strip()]
    line_count = len(lines)
    n_title = normalise(title)

    reasons = []

    # 1) Very long or very short
    if line_count > 150:
        reasons.append(f'very long ({line_count} lines)')
    if line_count < 5:
        reasons.append(f'very short ({line_count} lines)')

    # 2) Unusual source sites
    unusual = {
        'wikipedia.org': 'Wikipedia',
        'douyin.com': 'Douyin',
        'deezer.com': 'Deezer',
        'shazam.com': 'Shazam',
        'esquirehk.com': 'Esquire HK',
        'streetvoice.com': 'StreetVoice',
        'hot512.com': 'hot512',
        'hanmanhezi.com': 'hanmanhezi',
        'wiki.nryjbzm.cc': 'wiki mirror',
        'mmcuu.com': 'mmcuu',
        'lyricspros.com': 'lyricspros',
        'gecibook.com': 'gecibook',
        'jiosaavn.com': 'JioSaavn',
        'avsea.online': 'avsea (!!)',
        'song.corp.com.tw': 'song.corp',
    }
    for domain, label in unusual.items():
        if domain in url:
            reasons.append(f'unusual source: {label}')
            break

    # 3) Check if lyrics contain Chinese at all (for Chinese songs)
    has_chinese_title = any('\u4e00' <= c <= '\u9fff' for c in title)
    chinese_chars = sum(1 for c in lyric if '\u4e00' <= c <= '\u9fff')
    if has_chinese_title and chinese_chars < 20:
        reasons.append(f'very few Chinese chars ({chinese_chars})')

    # 4) Check if the URL contains a DIFFERENT song title
    # Decode the URL and look for song names
    decoded_url = unquote(url)
    # For appleofmyeye, mulanci etc. the URL sometimes has a different song name
    # Extract meaningful text segments from URL
    url_segments = re.findall(r'[\u4e00-\u9fff]+', decoded_url)
    if url_segments:
        # Check if any segment matches the title
        url_has_title = any(normalise(seg) == n_title or n_title in normalise(seg)
                           for seg in url_segments)
        # Check if URL has a DIFFERENT song title (long Chinese segment not matching)
        for seg in url_segments:
            ns = normalise(seg)
            if len(ns) >= 2 and ns != n_title and n_title not in ns and ns not in n_title:
                # Could be a different song - only flag if the segment looks like a title
                if len(seg) >= 3 and seg != singer:
                    # Might be singer name, skip those
                    singer_norm = normalise(singer)
                    if ns != singer_norm and singer_norm not in ns:
                        reasons.append(f'URL has "{seg}" (expected "{title}")')
                        break

    # 5) Check first lines for signs of a different song
    for line in lines[:10]:
        # Skip metadata lines
        if re.match(r'^(Lyricist|Composer|作詞|作曲|編曲|詞|曲)\s*[：:.]', line):
            continue
        # Look for a clear song title header that doesn't match
        m = re.match(r'^(.{2,20})\s*[-–—]\s*(.+)', line)
        if m:
            found_title = normalise(m.group(1))
            if found_title and found_title != n_title and n_title not in found_title:
                reasons.append(f'first lines have "{m.group(1).strip()}"')
                break

    if reasons:
        suspect.append({
            'id': rec['_id'],
            'title': title,
            'singer': singer,
            'lines': line_count,
            'url': url,
            'reasons': reasons,
            'first_3': lines[:3] if lines else [],
        })

# Print results
print(f'\nFlagged for manual check: {len(suspect)}')
print('=' * 80)
for s in suspect:
    print(f"\n[{s['id']}] {s['title']} - {s['singer']}  ({s['lines']} lines)")
    print(f"  URL: {s['url']}")
    print(f"  Reasons: {', '.join(s['reasons'])}")
    if s['first_3']:
        print(f"  First lines: {' | '.join(s['first_3'][:3])}")
