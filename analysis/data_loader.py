#!/usr/bin/env python3
"""
Shared data-loading utilities for all analysis modules.
Loads the checked lyrics CSV and singer metadata.
"""

import csv
import re
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CSV_PATH = os.path.join(DATA_DIR, 'checked_1986_2025_with_lyrics.csv')
META_PATH = os.path.join(DATA_DIR, 'singer_metadata.csv')


def load_songs():
    """Load all songs from the checked CSV. Returns list of dicts."""
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Clean up: strip whitespace, convert year to int
    for r in rows:
        r['Year'] = int(r['Year'])
        r['Lyrics'] = r['Lyrics'].strip()
        r['Title'] = r['Title'].strip()
        r['Singer'] = r['Singer'].strip()
        r['Lyricist'] = r['Lyricist'].strip()
    return rows


def load_singer_metadata():
    """Load singer metadata (gender, type). Returns dict keyed by Singer."""
    meta = {}
    with open(META_PATH, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            meta[row['Singer'].strip()] = {
                'gender': row['Gender'].strip(),
                'type': row['Type'].strip(),
            }
    return meta


def enrich_songs(songs, meta):
    """Add gender/type fields from metadata to each song dict."""
    for s in songs:
        m = meta.get(s['Singer'], {'gender': 'U', 'type': 'unknown'})
        s['Gender'] = m['gender']
        s['SingerType'] = m['type']
    return songs


def split_lines(lyrics):
    """Split lyrics into non-empty lines."""
    return [l.strip() for l in lyrics.split('\n') if l.strip()]


def split_sentences(lyrics):
    """Split lyrics into sentences by newlines and common punctuation."""
    text = re.sub(r'[，。！？、；：\n]+', '\n', lyrics)
    return [s.strip() for s in text.split('\n') if s.strip()]


def group_by_year(songs):
    """Group songs by year. Returns dict year -> list of songs."""
    result = {}
    for s in songs:
        result.setdefault(s['Year'], []).append(s)
    return result


def year_range(songs):
    """Return (min_year, max_year) from songs."""
    years = [s['Year'] for s in songs]
    return min(years), max(years)
