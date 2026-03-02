#!/usr/bin/env python3
"""
Cantonese vs Standard Written Chinese detection using cantonesedetect.

Analyses each line of lyrics and classifies as:
  - cantonese: distinctly Cantonese expression
  - swc: Standard Written Chinese / Mandarin-style
  - neutral: ambiguous / shared
  - mixed: contains both elements

Classical Chinese detection uses a combination of:
  - LIWC function-word density (classical Chinese tends to have fewer modern
    function words in LIWC)
  - A small curated marker list for well-known literary/classical particles
  - Regex patterns for classical constructions
"""

import re
from collections import Counter
from cantonesedetect import CantoneseDetector

from analysis.liwc_loader import get_liwc_dict


# ── Cantonese detection ───────────────────────────────────────────────────

_detector = CantoneseDetector()


def classify_line(line):
    """Classify a single line as cantonese/swc/neutral/mixed."""
    clean = line.strip()
    if not clean or len(clean) < 2:
        return 'neutral'
    return _detector.judge(clean)


def analyse_canto_swc(lyrics):
    """Classify every line and return aggregate statistics."""
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]
    classifications = []
    for line in lines:
        cls = classify_line(line)
        classifications.append({'line': line, 'class': cls})

    counts = Counter(c['class'] for c in classifications)
    total = len(classifications)

    return {
        'line_classifications': classifications,
        'counts': dict(counts),
        'total_lines': total,
        'cantonese_ratio': counts.get('cantonese', 0) / total if total else 0,
        'swc_ratio': counts.get('swc', 0) / total if total else 0,
        'neutral_ratio': counts.get('neutral', 0) / total if total else 0,
        'mixed_ratio': counts.get('mixed', 0) / total if total else 0,
    }


# ── Classical Chinese (文言) detection ────────────────────────────────────

# Core classical particles / function words rarely used in modern vernacular
_CLASSICAL_PARTICLES = [
    '之', '乎', '者', '也', '矣', '焉', '哉', '兮',
    '豈', '莫', '勿', '毋', '何以', '何故', '是以',
]

# Classical literary vocabulary common in pop lyrics
_CLASSICAL_VOCAB = [
    '歸去', '不復', '何處', '此生', '來生', '前世', '今世',
    '千秋', '萬載', '浮生', '紅塵', '塵世',
    '長恨', '離愁', '別緒', '相思', '相知',
    '無奈', '惘然', '悵然', '愴然', '黯然', '淒然',
    '纏綿', '繾綣', '旖旎', '婆娑', '斑斕',
    '滄桑', '輪迴', '涅槃', '無常', '因果',
]

# Patterns that suggest classical register
_CLASSICAL_PATTERNS = [
    r'不[復曾再]',
    r'何[處時人日]',
    r'莫[問說道非]',
    r'[縱即]使',
    r'[春秋冬夏][風雨雪月]',
]


def analyse_classical(lyrics, liwc_agg: dict = None):
    """Analyse classical Chinese content in lyrics.

    Uses curated markers + patterns supplemented by LIWC function-word
    density as a proxy signal (low modern function-word density in a line
    hints at classical register).
    """
    total_chars = sum(1 for c in lyrics if '\u4e00' <= c <= '\u9fff')

    # Marker counting
    marker_count = 0
    markers_found = []
    for marker in _CLASSICAL_PARTICLES + _CLASSICAL_VOCAB:
        n = lyrics.count(marker)
        if n > 0:
            marker_count += n
            markers_found.append((marker, n))

    # Pattern counting
    pattern_count = 0
    patterns_found = []
    for pat in _CLASSICAL_PATTERNS:
        matches = re.findall(pat, lyrics)
        if matches:
            pattern_count += len(matches)
            patterns_found.extend(matches)

    total_classical = marker_count + pattern_count

    # LIWC supplement: if we have aggregate, compute ratio of classical
    # markers to modern function words
    liwc_function_ratio = None
    if liwc_agg is not None:
        func_count = liwc_agg.get('function', 0)
        total_liwc = sum(liwc_agg.values())
        if total_liwc > 0:
            liwc_function_ratio = func_count / total_liwc

    result = {
        'classical_marker_count': marker_count,
        'classical_pattern_count': pattern_count,
        'classical_total': total_classical,
        'classical_density': total_classical / total_chars if total_chars else 0,
        'markers_found': markers_found,
        'patterns_found': patterns_found,
    }
    if liwc_function_ratio is not None:
        result['liwc_function_ratio'] = liwc_function_ratio

    return result


# ── Combined register analysis ───────────────────────────────────────────

def analyse_register(lyrics, liwc_agg: dict = None):
    """Full register analysis: Cantonese vs SWC + classical elements."""
    canto = analyse_canto_swc(lyrics)
    classical = analyse_classical(lyrics, liwc_agg=liwc_agg)
    return {
        'cantonese_swc': canto,
        'classical': classical,
    }
