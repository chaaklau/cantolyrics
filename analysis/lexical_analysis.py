#!/usr/bin/env python3
"""
Lexical analysis for Cantonese pop lyrics.

Core metrics:
  - Character frequency & TTR
  - Word segmentation via jieba + word TTR
  - Reduplication / repetition analysis
  - Non-Chinese content detection (English, Japanese, Korean)

LIWC-based metrics (replaces fixed vocabulary):
  - LIWC category profiling per song (function, affect, social, cogproc …)
  - Day/night via targeted sub-matching
"""

import re
from collections import Counter
import jieba

from analysis.liwc_loader import get_liwc_dict, analyse_song_liwc


# ── Day/Night cues (minimal targeted sets for temporal sub-dimension) ─────

_DAY_CUES = set('日 天 朝 晨 晝 午 陽 曙 黎明 清晨 早上 白天 下午 正午 日光 日出 陽光 天光 朝陽 晨曦'.split())
_NIGHT_CUES = set('夜 晚 暮 昏 月 宵 黃昏 夜晚 深夜 月光 月亮 星光 星 夜空 黑夜 暮色 晚上 宵夜 月色 星空'.split())


def char_frequency(text):
    """Count CJK character frequencies. Returns Counter."""
    chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
    return Counter(chars)


def unique_char_count(text):
    """Count unique CJK characters."""
    chars = set(c for c in text if '\u4e00' <= c <= '\u9fff')
    return len(chars)


def total_char_count(text):
    """Count total CJK characters."""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def char_ttr(text):
    """Type-Token Ratio at character level."""
    total = total_char_count(text)
    unique = unique_char_count(text)
    return unique / total if total > 0 else 0


# ── Word-level analysis (jieba) ───────────────────────────────────────────

def segment_words(text):
    """Segment text into words using jieba. Returns list of words."""
    # Remove non-CJK and non-alpha
    clean = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
    words = list(jieba.cut(clean))
    return [w.strip() for w in words if w.strip() and len(w.strip()) > 0]


def word_frequency(text):
    """Word frequency after segmentation. Returns Counter."""
    words = segment_words(text)
    return Counter(words)


def word_ttr(text):
    """Type-Token Ratio at word level."""
    words = segment_words(text)
    if not words:
        return 0
    return len(set(words)) / len(words)


def morpheme_count(text):
    """Approximate morpheme count (= CJK character count, since Chinese is
    largely morphosyllabic)."""
    return total_char_count(text)


# ── Day/Night analysis ────────────────────────────────────────────────────

def day_night_ratio(text):
    """Count day vs night cue words using targeted temporal lists."""
    day_count = sum(text.count(w) for w in _DAY_CUES)
    night_count = sum(text.count(w) for w in _NIGHT_CUES)
    total = day_count + night_count
    return {
        'day_count': day_count,
        'night_count': night_count,
        'ratio': day_count / night_count if night_count > 0 else (float('inf') if day_count > 0 else 0),
        'day_pct': day_count / total if total > 0 else 0.5,
    }


# ── Reduplication / repetition analysis ───────────────────────────────────

def find_reduplication(text):
    """Find single-char reduplication (疊字) like AA patterns.
    Returns list of (char, count) pairs."""
    # Find consecutive identical CJK chars (AA, AAA, etc.)
    pattern = re.compile(r'([\u4e00-\u9fff])\1+')
    matches = pattern.findall(text)
    return Counter(matches)


def find_word_repetition(lyrics):
    """Find repeated words/phrases in lyrics.
    Returns dict with char_reduplication, word_repetition, line_repetition."""
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]

    # Character-level reduplication (AA)
    char_redup = find_reduplication(lyrics)

    # Line repetition
    line_counter = Counter(lines)
    repeated_lines = {l: c for l, c in line_counter.items() if c > 1}

    # Word-level repetition (segmented)
    words = segment_words(lyrics)
    word_counter = Counter(words)
    # Filter to multi-char words appearing 3+ times
    repeated_words = {w: c for w, c in word_counter.items()
                      if len(w) > 1 and c >= 3}

    return {
        'char_reduplication_count': sum(char_redup.values()),
        'char_reduplication_types': len(char_redup),
        'char_reduplication_examples': char_redup.most_common(10),
        'repeated_lines': len(repeated_lines),
        'total_lines': len(lines),
        'line_repetition_ratio': len(repeated_lines) / len(lines) if lines else 0,
        'top_repeated_words': sorted(repeated_words.items(), key=lambda x: -x[1])[:15],
    }


# ── Non-CJK content detection ────────────────────────────────────────────

def count_english_words(text):
    """Count English/alphabetic words in lyrics."""
    return len(re.findall(r'[a-zA-Z]+', text))


def count_alpha_ratio(text):
    """Ratio of alphabetic characters to total characters."""
    alpha = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    total = len(text.replace('\n', '').replace(' ', ''))
    return alpha / total if total > 0 else 0


def detect_non_chinese(text):
    """Detect non-Chinese scripts: English, Japanese kana, Korean hangul."""
    english = re.findall(r'[a-zA-Z]+', text)
    # Japanese hiragana & katakana
    hiragana = re.findall(r'[\u3040-\u309f]+', text)
    katakana = re.findall(r'[\u30a0-\u30ff]+', text)
    # Korean hangul
    hangul = re.findall(r'[\uac00-\ud7af]+', text)

    return {
        'english_words': english,
        'english_count': len(english),
        'japanese_segments': hiragana + katakana,
        'japanese_count': len(hiragana) + len(katakana),
        'korean_segments': hangul,
        'korean_count': len(hangul),
    }


# ── Aggregate per-song analysis ──────────────────────────────────────────

def analyse_song_lexical(lyrics):
    """Run all lexical analyses on one song's lyrics."""
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]
    total_chars = total_char_count(lyrics)

    # LIWC profiling
    liwc_result = analyse_song_liwc(lyrics)

    return {
        'total_chars': total_chars,
        'unique_chars': unique_char_count(lyrics),
        'char_ttr': char_ttr(lyrics),
        'word_ttr': word_ttr(lyrics),
        'morpheme_count': morpheme_count(lyrics),
        'line_count': len(lines),
        'avg_line_length': total_chars / len(lines) if lines else 0,
        'day_night': day_night_ratio(lyrics),
        'reduplication': find_word_repetition(lyrics),
        'non_chinese': detect_non_chinese(lyrics),
        'english_word_count': count_english_words(lyrics),
        # LIWC outputs
        'liwc': {
            'total_words': liwc_result['total_words'],
            'match_ratio': liwc_result['match_ratio'],
            'aggregate': liwc_result['aggregate'],
            'normalised': liwc_result['normalised'],
            'top_categories': liwc_result['top_categories'],
        },
    }
