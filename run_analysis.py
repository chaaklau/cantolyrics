#!/usr/bin/env python3
"""
Main analysis pipeline for Cantonese pop lyrics.

Runs all analyses on the checked dataset and outputs:
  - data/analysis_results.json  (per-song results)
  - data/yearly_summary.json    (aggregated by year)
  - data/overall_summary.json   (global statistics)

Usage:
    python3 run_analysis.py
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from analysis.data_loader import (
    load_songs, load_singer_metadata, enrich_songs,
    split_lines, group_by_year, year_range,
)
from analysis.jyutping_analysis import (
    analyse_tones, analyse_tone_jumps, analyse_rhyme,
)
from analysis.lexical_analysis import analyse_song_lexical
from analysis.register_analysis import analyse_register
from analysis.sentiment_analysis import (
    analyse_sentiment, analyse_themes, detect_places,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def analyse_one_song(song):
    """Run all analyses on a single song. Returns analysis dict."""
    lyrics = song['Lyrics']
    if not lyrics or len(lyrics.strip()) < 10:
        return None

    result = {
        'id': song['ID'],
        'title': song['Title'],
        'singer': song['Singer'],
        'year': song['Year'],
        'lyricist': song['Lyricist'],
        'gender': song.get('Gender', 'U'),
        'singer_type': song.get('SingerType', 'unknown'),
    }

    # Basic stats
    lines = split_lines(lyrics)
    result['line_count'] = len(lines)
    result['lyrics_length'] = len(lyrics)

    # Jyutping / phonological
    try:
        tones = analyse_tones(lyrics)
        result['tones'] = {
            'total': tones['total'],
            'proportions': {str(k): round(v, 4) for k, v in tones['proportions'].items()},
        }
    except Exception as e:
        result['tones'] = {'error': str(e)}

    try:
        jumps = analyse_tone_jumps(lyrics)
        result['tone_jumps'] = {
            'avg_jump': round(jumps['avg_jump'], 4),
            'large_jump_ratio': round(jumps['large_jump_ratio'], 4),
            'total_pairs': jumps['total_pairs'],
        }
    except Exception as e:
        result['tone_jumps'] = {'error': str(e)}

    try:
        rhyme = analyse_rhyme(lyrics)
        result['rhyme'] = {
            'rhyme_ratio': round(rhyme['rhyme_ratio'], 4),
            'entering_ratio': round(rhyme['entering_ratio'], 4),
            'total_line_endings': rhyme['total_line_endings'],
            'top_finals': rhyme['top_finals'][:5],
        }
    except Exception as e:
        result['rhyme'] = {'error': str(e)}

    # Lexical (includes LIWC profiling)
    liwc_agg = {}
    try:
        lex = analyse_song_lexical(lyrics)
        liwc_agg = lex.get('liwc', {}).get('aggregate', {})
        result['lexical'] = {
            'total_chars': lex['total_chars'],
            'unique_chars': lex['unique_chars'],
            'char_ttr': round(lex['char_ttr'], 4),
            'word_ttr': round(lex['word_ttr'], 4),
            'morpheme_count': lex['morpheme_count'],
            'line_count': lex['line_count'],
            'avg_line_length': round(lex['avg_line_length'], 2),
            'english_word_count': lex['english_word_count'],
            'day_night': lex['day_night'],
            'reduplication': {
                'char_redup_count': lex['reduplication']['char_reduplication_count'],
                'char_redup_types': lex['reduplication']['char_reduplication_types'],
                'char_redup_examples': lex['reduplication']['char_reduplication_examples'],
                'repeated_lines': lex['reduplication']['repeated_lines'],
                'line_repetition_ratio': round(lex['reduplication']['line_repetition_ratio'], 4),
            },
            'non_chinese': {
                'english_count': lex['non_chinese']['english_count'],
                'japanese_count': lex['non_chinese']['japanese_count'],
                'korean_count': lex['non_chinese']['korean_count'],
            },
            'liwc': {
                'total_words': lex['liwc']['total_words'],
                'match_ratio': round(lex['liwc']['match_ratio'], 4),
                'top_categories': lex['liwc']['top_categories'][:15],
                'normalised': {k: round(v, 6) for k, v in lex['liwc']['normalised'].items()},
            },
        }
    except Exception as e:
        result['lexical'] = {'error': str(e)}

    # Register (Cantonese vs SWC + classical) — pass liwc_agg
    try:
        reg = analyse_register(lyrics, liwc_agg=liwc_agg)
        canto = reg['cantonese_swc']
        result['register'] = {
            'cantonese_ratio': round(canto['cantonese_ratio'], 4),
            'swc_ratio': round(canto['swc_ratio'], 4),
            'neutral_ratio': round(canto['neutral_ratio'], 4),
            'mixed_ratio': round(canto['mixed_ratio'], 4),
            'counts': canto['counts'],
        }
        cl = reg['classical']
        result['classical'] = {
            'density': round(cl['classical_density'], 6),
            'marker_count': cl['classical_marker_count'],
            'pattern_count': cl['classical_pattern_count'],
        }
        if 'liwc_function_ratio' in cl:
            result['classical']['liwc_function_ratio'] = round(cl['liwc_function_ratio'], 4)
    except Exception as e:
        result['register'] = {'error': str(e)}
        result['classical'] = {'error': str(e)}

    # Sentiment & themes — pass liwc_agg to avoid recomputation
    try:
        sent = analyse_sentiment(lyrics, liwc_agg=liwc_agg)
        result['sentiment'] = {
            'score': round(sent['score'], 4),
            'label': sent['label'],
            'positive_count': sent['positive_count'],
            'negative_count': sent['negative_count'],
            'snownlp_score': round(sent['snownlp_score'], 4),
            'dominant_emotion': sent['dominant_emotion'],
            'emotions': sent['emotions'],
        }
    except Exception as e:
        result['sentiment'] = {'error': str(e)}

    try:
        themes = analyse_themes(lyrics, liwc_agg=liwc_agg)
        result['themes'] = {
            'primary': themes['primary_theme'],
            'secondary': themes['secondary_theme'],
            'counts': themes['theme_counts'],
            'percentages': {k: round(v, 4) for k, v in themes['theme_percentages'].items()},
        }
    except Exception as e:
        result['themes'] = {'error': str(e)}

    try:
        places = detect_places(lyrics)
        result['places'] = places
    except Exception as e:
        result['places'] = {'error': str(e)}

    return result


def compute_yearly_summary(song_results):
    """Aggregate per-song results into yearly summaries.

    Includes per-song value arrays for boxplot visualisation.
    """
    by_year = defaultdict(list)
    for r in song_results:
        by_year[r['year']].append(r)

    yearly = {}
    for year in sorted(by_year):
        songs = by_year[year]
        n = len(songs)

        # Helper for safe averaging
        def avg(key_fn, default=0):
            vals = [key_fn(s) for s in songs if key_fn(s) is not None]
            return sum(vals) / len(vals) if vals else default

        def safe_get(s, *keys, default=None):
            obj = s
            for k in keys:
                if isinstance(obj, dict) and k in obj:
                    obj = obj[k]
                else:
                    return default
            return obj

        def collect(key_fn):
            """Collect per-song values for boxplot data."""
            return [v for v in (key_fn(s) for s in songs) if v is not None]

        summary = {
            'year': year,
            'song_count': n,
            # Gender distribution
            'gender_counts': dict(Counter(s['gender'] for s in songs)),
            'type_counts': dict(Counter(s['singer_type'] for s in songs)),
            # Avg lyrics length
            'avg_total_chars': round(avg(lambda s: safe_get(s, 'lexical', 'total_chars')), 1),
            'avg_unique_chars': round(avg(lambda s: safe_get(s, 'lexical', 'unique_chars')), 1),
            'avg_line_count': round(avg(lambda s: safe_get(s, 'lexical', 'line_count')), 1),
            'avg_char_ttr': round(avg(lambda s: safe_get(s, 'lexical', 'char_ttr')), 4),
            'avg_word_ttr': round(avg(lambda s: safe_get(s, 'lexical', 'word_ttr')), 4),
            # Phonological
            'avg_rhyme_ratio': round(avg(lambda s: safe_get(s, 'rhyme', 'rhyme_ratio')), 4),
            'avg_entering_ratio': round(avg(lambda s: safe_get(s, 'rhyme', 'entering_ratio')), 4),
            'avg_large_jump_ratio': round(avg(lambda s: safe_get(s, 'tone_jumps', 'large_jump_ratio')), 4),
            # Register
            'avg_cantonese_ratio': round(avg(lambda s: safe_get(s, 'register', 'cantonese_ratio')), 4),
            'avg_swc_ratio': round(avg(lambda s: safe_get(s, 'register', 'swc_ratio')), 4),
            'avg_classical_density': round(avg(lambda s: safe_get(s, 'classical', 'density')), 6),
            # Lexical
            'avg_english_words': round(avg(lambda s: safe_get(s, 'lexical', 'english_word_count')), 2),
            'avg_redup_count': round(avg(lambda s: safe_get(s, 'lexical', 'reduplication', 'char_redup_count')), 2),
            'avg_line_rep_ratio': round(avg(lambda s: safe_get(s, 'lexical', 'reduplication', 'line_repetition_ratio')), 4),
            # LIWC match ratio
            'avg_liwc_match_ratio': round(avg(lambda s: safe_get(s, 'lexical', 'liwc', 'match_ratio')), 4),
            # Day/Night
            'total_day': sum(safe_get(s, 'lexical', 'day_night', 'day_count', default=0) for s in songs),
            'total_night': sum(safe_get(s, 'lexical', 'day_night', 'night_count', default=0) for s in songs),
            # Sentiment
            'avg_sentiment': round(avg(lambda s: safe_get(s, 'sentiment', 'score')), 4),
            'avg_snownlp': round(avg(lambda s: safe_get(s, 'sentiment', 'snownlp_score')), 4),
            'sentiment_dist': dict(Counter(safe_get(s, 'sentiment', 'label', default='unknown') for s in songs)),
            'emotion_totals': {},
            # Themes
            'theme_dist': dict(Counter(safe_get(s, 'themes', 'primary', default='none') for s in songs)),
            # Non-Chinese
            'total_english': sum(safe_get(s, 'lexical', 'non_chinese', 'english_count', default=0) for s in songs),
            'total_japanese': sum(safe_get(s, 'lexical', 'non_chinese', 'japanese_count', default=0) for s in songs),
            'total_korean': sum(safe_get(s, 'lexical', 'non_chinese', 'korean_count', default=0) for s in songs),
            # Places
            'places': defaultdict(int),

            # ── Per-song value arrays for boxplots ──
            'boxplot_data': {
                'char_ttr': collect(lambda s: safe_get(s, 'lexical', 'char_ttr')),
                'word_ttr': collect(lambda s: safe_get(s, 'lexical', 'word_ttr')),
                'total_chars': collect(lambda s: safe_get(s, 'lexical', 'total_chars')),
                'sentiment_score': collect(lambda s: safe_get(s, 'sentiment', 'score')),
                'snownlp_score': collect(lambda s: safe_get(s, 'sentiment', 'snownlp_score')),
                'cantonese_ratio': collect(lambda s: safe_get(s, 'register', 'cantonese_ratio')),
                'rhyme_ratio': collect(lambda s: safe_get(s, 'rhyme', 'rhyme_ratio')),
                'entering_ratio': collect(lambda s: safe_get(s, 'rhyme', 'entering_ratio')),
                'classical_density': collect(lambda s: safe_get(s, 'classical', 'density')),
                'line_rep_ratio': collect(lambda s: safe_get(s, 'lexical', 'reduplication', 'line_repetition_ratio')),
                'liwc_match_ratio': collect(lambda s: safe_get(s, 'lexical', 'liwc', 'match_ratio')),
            },
        }

        # Aggregate emotions
        emotion_keys = ['joy', 'sadness', 'anger', 'love', 'anxiety', 'nostalgia', 'loneliness', 'hope']
        for ek in emotion_keys:
            summary['emotion_totals'][ek] = sum(
                safe_get(s, 'sentiment', 'emotions', ek, default=0) for s in songs
            )

        # Aggregate places
        for s in songs:
            if isinstance(s.get('places'), dict):
                for region, places_list in s['places'].items():
                    if region == 'error':
                        continue
                    for place, count in places_list:
                        summary['places'][region] += count
        summary['places'] = dict(summary['places'])

        yearly[year] = summary

    return yearly


def compute_overall_summary(song_results, yearly):
    """Compute global statistics."""
    n = len(song_results)
    years = sorted(yearly.keys())

    # Top lyricists
    lyricist_counter = Counter(s['lyricist'] for s in song_results)
    # Top singers
    singer_counter = Counter(s['singer'] for s in song_results)

    # All place mentions
    all_places = defaultdict(Counter)
    for s in song_results:
        if isinstance(s.get('places'), dict):
            for region, plist in s['places'].items():
                if region == 'error':
                    continue
                for place, count in plist:
                    all_places[region][place] += count

    # Aggregate LIWC top categories across all songs
    liwc_totals = Counter()
    for s in song_results:
        norm = s.get('lexical', {}).get('liwc', {}).get('normalised', {})
        if isinstance(norm, dict):
            for cat, val in norm.items():
                liwc_totals[cat] += val

    return {
        'total_songs': n,
        'year_range': [years[0], years[-1]] if years else [],
        'top_singers': singer_counter.most_common(30),
        'top_lyricists': lyricist_counter.most_common(30),
        'gender_overall': dict(Counter(s['gender'] for s in song_results)),
        'all_places': {r: dict(c) for r, c in all_places.items()},
        'liwc_avg_proportions': {cat: round(val / n, 6) for cat, val in liwc_totals.most_common(30)} if n else {},
    }


def main():
    print('=' * 60)
    print('Cantonese Pop Lyrics Analysis Pipeline')
    print('=' * 60)

    # Load data
    print('\n[1/4] Loading data...')
    songs = load_songs()
    meta = load_singer_metadata()
    songs = enrich_songs(songs, meta)
    print(f'  Loaded {len(songs)} songs, {len(meta)} singer metadata entries.')

    # Check for missing metadata
    missing = [s['Singer'] for s in songs if s.get('Gender') == 'U']
    if missing:
        print(f'  WARNING: {len(set(missing))} singers missing metadata: {set(missing)}')

    # Run per-song analysis
    print('\n[2/4] Analysing songs...')
    results = []
    t0 = time.time()
    for i, song in enumerate(songs):
        r = analyse_one_song(song)
        if r:
            results.append(r)
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f'  {i + 1}/{len(songs)} songs analysed ({elapsed:.1f}s)')

    elapsed = time.time() - t0
    print(f'  Done: {len(results)} songs analysed in {elapsed:.1f}s')

    # Yearly summary
    print('\n[3/4] Computing yearly summaries...')
    yearly = compute_yearly_summary(results)
    print(f'  {len(yearly)} years summarised.')

    # Overall summary
    overall = compute_overall_summary(results, yearly)

    # Save
    print('\n[4/4] Saving results...')

    with open(os.path.join(DATA_DIR, 'analysis_results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f'  Saved analysis_results.json ({len(results)} songs)')

    with open(os.path.join(DATA_DIR, 'yearly_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(yearly, f, ensure_ascii=False, indent=1)
    print(f'  Saved yearly_summary.json ({len(yearly)} years)')

    with open(os.path.join(DATA_DIR, 'overall_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(overall, f, ensure_ascii=False, indent=1)
    print('  Saved overall_summary.json')

    print('\nDone!')
    return results, yearly, overall


if __name__ == '__main__':
    main()
