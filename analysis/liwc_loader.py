#!/usr/bin/env python3
"""
LIWC dictionary loader and per-line / per-song profiler.

Loads the Cantonese LIWC word list from tool/canto-liwc-temp.csv.
Supports:
  - Exact word matching
  - Wildcard prefix matching (words ending with *)
  - Per-line LIWC profiling  (category hit counts per line)
  - Per-song LIWC profiling  (aggregated category proportions)
"""

import csv
import os
import re
from collections import Counter, defaultdict

import jieba

# ── Load dictionary ──────────────────────────────────────────────────────

_LIWC_PATH = os.path.join(os.path.dirname(__file__), '..', 'tool', 'canto-liwc-temp.csv')

# Category hierarchy: child → parent mapping for LIWC
# This mirrors the standard LIWC-22 hierarchy.
CATEGORY_PARENTS = {
    'pronoun': 'function', 'ppron': 'pronoun', 'ipron': 'pronoun',
    'article': 'function', 'prep': 'function', 'auxverb': 'function',
    'adverb': 'function', 'conj': 'function', 'negate': 'function',
    'verb': 'function', 'adj': 'function', 'compare': 'function',
    'interrog': 'function', 'number': 'function', 'quant': 'function',
    'posemo': 'affect', 'negemo': 'affect', 'anx': 'negemo',
    'anger': 'negemo', 'sad': 'negemo',
    'social': None, 'family': 'social', 'friend': 'social',
    'female': 'social', 'male': 'social',
    'cogproc': None, 'insight': 'cogproc', 'cause': 'cogproc',
    'discrep': 'cogproc', 'tentat': 'cogproc', 'certain': 'cogproc',
    'differ': 'cogproc',
    'percept': None, 'see': 'percept', 'hear': 'percept', 'feel': 'percept',
    'bio': None, 'body': 'bio', 'health': 'bio', 'sexual': 'bio',
    'ingest': 'bio',
    'drives': None, 'affiliation': 'drives', 'achieve': 'drives',
    'power': 'drives', 'reward': 'drives', 'risk': 'drives',
    'relativ': None, 'motion': 'relativ', 'space': 'relativ',
    'time': 'relativ',
    'work': None, 'leisure': None, 'home': None, 'money': None,
    'relig': None, 'death': None, 'informal': None,
    'swear': 'informal', 'netspeak': 'informal', 'assent': 'informal',
    'nonflu': 'informal', 'filler': 'informal',
}

# Sentiment-relevant categories
SENTIMENT_CATEGORIES = {'posemo', 'negemo', 'anx', 'anger', 'sad', 'affect'}

# Emotion-mapping from LIWC categories to emotion labels
LIWC_EMOTION_MAP = {
    'posemo': 'joy',
    'negemo': 'sadness',
    'anger': 'anger',
    'anx': 'anxiety',
    'sad': 'sadness',
    'affect': 'affect',
}


class LIWCDictionary:
    """Loads the LIWC dictionary and provides matching functions."""

    def __init__(self, path=None):
        self.path = path or _LIWC_PATH
        # word (exact) → set of category_short
        self.exact: dict[str, set[str]] = defaultdict(set)
        # prefix (without trailing *) → set of category_short
        self.prefix: dict[str, set[str]] = defaultdict(set)
        # All category short names seen
        self.categories: set[str] = set()
        # Category metadata: short → full name
        self.category_names: dict[str, str] = {}

        self._load()

    def _load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get('Word', '').strip()
                keep = row.get('Keep', '').strip().lower()
                cat_id = row.get('Category_ID', '').strip()
                cat_short = row.get('Category_Short', '').strip()
                cat_full = row.get('Category_Full', '').strip()

                # Skip instruction rows and non-kept entries
                if keep != 'true':
                    continue
                if not cat_id.isdigit():
                    continue
                if not word or not cat_short:
                    continue

                self.categories.add(cat_short)
                if cat_full:
                    self.category_names[cat_short] = cat_full

                if word.endswith('*'):
                    self.prefix[word[:-1]].add(cat_short)
                else:
                    self.exact[word].add(cat_short)

    def match_word(self, word: str) -> set[str]:
        """Return set of LIWC categories that match a word."""
        cats = set()
        # Exact match
        if word in self.exact:
            cats.update(self.exact[word])
        # Prefix match: check if any prefix is a prefix of this word
        for pfx, pfx_cats in self.prefix.items():
            if word.startswith(pfx) and len(word) > len(pfx):
                cats.update(pfx_cats)
        return cats

    def profile_words(self, words: list[str]) -> dict[str, int]:
        """Given a list of segmented words, return category → hit count."""
        counts = Counter()
        for w in words:
            cats = self.match_word(w)
            for c in cats:
                counts[c] += 1
        return dict(counts)

    def profile_text(self, text: str) -> dict[str, int]:
        """Segment text with jieba and return LIWC category counts."""
        words = self._segment(text)
        return self.profile_words(words)

    def profile_text_normalised(self, text: str) -> dict[str, float]:
        """Return category proportions (count / total_words)."""
        words = self._segment(text)
        total = len(words)
        if total == 0:
            return {}
        counts = self.profile_words(words)
        return {cat: cnt / total for cat, cnt in counts.items()}

    @staticmethod
    def _segment(text: str) -> list[str]:
        """Segment Chinese text, keeping CJK and alpha tokens."""
        clean = re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbf\w]', ' ', text)
        words = jieba.cut(clean)
        return [w.strip() for w in words if w.strip()]


# ── Module-level singleton ────────────────────────────────────────────────

_dict_instance: LIWCDictionary | None = None


def get_liwc_dict() -> LIWCDictionary:
    """Return a cached LIWCDictionary singleton."""
    global _dict_instance
    if _dict_instance is None:
        _dict_instance = LIWCDictionary()
    return _dict_instance


# ── Per-line analysis ─────────────────────────────────────────────────────

def analyse_line_liwc(line: str, liwc: LIWCDictionary | None = None) -> dict:
    """Analyse a single line of lyrics with LIWC.
    Returns dict with word_count, categories (counts), matched_words."""
    if liwc is None:
        liwc = get_liwc_dict()
    words = liwc._segment(line)
    profile = liwc.profile_words(words)
    matched = sum(1 for w in words if liwc.match_word(w))
    return {
        'word_count': len(words),
        'matched_word_count': matched,
        'categories': profile,
    }


def analyse_song_liwc(lyrics: str, liwc: LIWCDictionary | None = None) -> dict:
    """Full per-line LIWC analysis for one song.

    Returns:
        per_line: list of per-line results
        aggregate: category counts summed across all lines
        normalised: category proportions (count / total_words)
        sentiment_score: (posemo - negemo) / (posemo + negemo)
        top_categories: sorted list of (cat, count)
    """
    if liwc is None:
        liwc = get_liwc_dict()

    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]

    # Aggregate across all lines
    total_words = 0
    total_matched = 0
    agg = Counter()

    for line in lines:
        result = analyse_line_liwc(line, liwc)
        total_words += result['word_count']
        total_matched += result['matched_word_count']
        for cat, cnt in result['categories'].items():
            agg[cat] += cnt

    # Normalise
    normalised = {cat: cnt / total_words for cat, cnt in agg.items()} if total_words > 0 else {}

    # Sentiment from LIWC
    posemo = agg.get('posemo', 0)
    negemo = agg.get('negemo', 0)
    affect_total = posemo + negemo
    sentiment_score = (posemo - negemo) / affect_total if affect_total > 0 else 0.0

    # Emotion profile from LIWC
    emotions = {}
    for cat, label in LIWC_EMOTION_MAP.items():
        if cat in agg:
            emotions[label] = emotions.get(label, 0) + agg[cat]

    # Top categories
    top = sorted(agg.items(), key=lambda x: -x[1])

    return {
        'total_words': total_words,
        'total_matched': total_matched,
        'match_ratio': total_matched / total_words if total_words > 0 else 0,
        'aggregate': dict(agg),
        'normalised': normalised,
        'sentiment_score': sentiment_score,
        'posemo_count': posemo,
        'negemo_count': negemo,
        'emotions': emotions,
        'top_categories': top[:20],
    }
