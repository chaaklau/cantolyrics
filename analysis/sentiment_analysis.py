#!/usr/bin/env python3
"""
Sentiment, emotion, theme, and place-name analysis for Cantonese lyrics.

Approach:
  - Sentiment: LIWC posemo/negemo as primary signal, SnowNLP as supplementary
  - Emotions:  LIWC affect sub-categories (anger, anx, sad, posemo)
  - Themes:    LIWC higher-level categories (social, drives, cogproc, relig,
               death, bio, work, leisure, home, money) + targeted keyword sets
  - Places:    spaCy zh_core_web_sm NER (GPE, LOC, FAC) with fallback list
"""

import re
from collections import Counter, defaultdict

from snownlp import SnowNLP
import spacy

from analysis.liwc_loader import get_liwc_dict, analyse_song_liwc


# ── Lazy-loaded singletons ────────────────────────────────────────────────

_nlp = None


def _get_nlp():
    """Return cached spaCy model. Prefers zh_core_web_trf for better NER."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load('zh_core_web_trf')
        except OSError:
            _nlp = spacy.load('zh_core_web_sm')
    return _nlp


# ── LIWC-based sentiment ─────────────────────────────────────────────────

def sentiment_liwc(liwc_agg: dict) -> dict:
    """Compute sentiment from pre-computed LIWC aggregate counts.

    Returns score in [-1, 1] and label positive/negative/neutral.
    """
    posemo = liwc_agg.get('posemo', 0)
    negemo = liwc_agg.get('negemo', 0)
    total = posemo + negemo
    score = (posemo - negemo) / total if total > 0 else 0.0
    if score > 0.15:
        label = 'positive'
    elif score < -0.15:
        label = 'negative'
    else:
        label = 'neutral'
    return {
        'score': score,
        'label': label,
        'posemo_count': posemo,
        'negemo_count': negemo,
    }


# ── SnowNLP supplementary sentiment ──────────────────────────────────────

def sentiment_snownlp(lyrics: str) -> float:
    """Per-line SnowNLP sentiment, averaged across non-empty lines.

    Returns value in [0, 1] where >0.5 = positive.
    """
    lines = [l.strip() for l in lyrics.split('\n') if l.strip() and len(l.strip()) >= 2]
    if not lines:
        return 0.5
    scores = []
    for line in lines:
        try:
            scores.append(SnowNLP(line).sentiments)
        except Exception:
            continue
    return sum(scores) / len(scores) if scores else 0.5


# ── Emotion profile from LIWC ────────────────────────────────────────────

def emotion_profile_liwc(liwc_agg: dict) -> dict:
    """Map LIWC categories to emotion dimensions."""
    return {
        'joy': liwc_agg.get('posemo', 0),
        'sadness': liwc_agg.get('sad', 0),
        'anger': liwc_agg.get('anger', 0),
        'anxiety': liwc_agg.get('anx', 0),
        'love': liwc_agg.get('affiliation', 0),
        'nostalgia': liwc_agg.get('time', 0),       # temporal references as proxy
        'loneliness': liwc_agg.get('sad', 0),        # overlap with sadness
        'hope': liwc_agg.get('achieve', 0),
    }


# ── Combined sentiment analysis ──────────────────────────────────────────

def analyse_sentiment(lyrics: str, liwc_agg: dict = None) -> dict:
    """Full sentiment analysis for one song.

    If liwc_agg is provided (from lexical analysis), re-uses it.
    Otherwise computes LIWC from scratch.
    """
    if liwc_agg is None:
        liwc_result = analyse_song_liwc(lyrics)
        liwc_agg = liwc_result['aggregate']

    sent = sentiment_liwc(liwc_agg)
    snlp = sentiment_snownlp(lyrics)
    emotions = emotion_profile_liwc(liwc_agg)

    # Dominant emotion
    dominant = max(emotions, key=emotions.get) if any(emotions.values()) else 'none'

    return {
        'score': sent['score'],
        'label': sent['label'],
        'positive_count': sent['posemo_count'],
        'negative_count': sent['negemo_count'],
        'snownlp_score': snlp,
        'emotions': emotions,
        'dominant_emotion': dominant,
    }


# ── Theme analysis (LIWC categories as themes) ───────────────────────────

# Map LIWC categories to thematic labels
_THEME_MAP = {
    'romantic_love': ['affiliation', 'sexual', 'posemo'],
    'heartbreak':    ['sad', 'negemo', 'anger'],
    'self_identity': ['i', 'cogproc', 'insight', 'differ'],
    'friendship':    ['social', 'affiliation', 'friend'],
    'society':       ['power', 'risk', 'social', 'achieve'],
    'nature':        ['percept', 'see', 'hear', 'feel', 'bio'],
    'nostalgia':     ['time', 'relativ'],
    'existential':   ['death', 'relig', 'cogproc'],
    'work_life':     ['work', 'money', 'achieve'],
    'leisure':       ['leisure', 'home'],
}


def analyse_themes(lyrics: str, liwc_agg: dict = None) -> dict:
    """Detect thematic content via LIWC category mapping.

    If liwc_agg is provided, re-uses it.
    """
    if liwc_agg is None:
        liwc_result = analyse_song_liwc(lyrics)
        liwc_agg = liwc_result['aggregate']

    theme_scores = {}
    for theme, cats in _THEME_MAP.items():
        theme_scores[theme] = sum(liwc_agg.get(c, 0) for c in cats)

    total = sum(theme_scores.values())
    theme_pcts = {t: c / total if total else 0 for t, c in theme_scores.items()}

    ranked = sorted(theme_scores.items(), key=lambda x: -x[1])

    return {
        'theme_counts': theme_scores,
        'theme_percentages': theme_pcts,
        'primary_theme': ranked[0][0] if ranked and ranked[0][1] > 0 else 'none',
        'secondary_theme': ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else 'none',
    }


# ── Place name detection via spaCy NER ────────────────────────────────────

# Fallback list – only used when NER misses well-known HK places
_HK_PLACES_FALLBACK = {
    '維港', '獅子山', '太平山', '大嶼山', '馬鞍山', '天水圍',
    '南丫島', '長洲', '大澳', '石澳', '西貢', '赤柱', '淺水灣',
    '海洋公園', '迪士尼',
}

# Region classifier by entity text
_REGION_KEYWORDS = {
    'hong_kong': ['香港', '維港', '維多利亞', '旺角', '尖沙咀', '銅鑼灣', '中環',
                  '太平山', '獅子山', '大嶼山', '九龍', '新界', '灣仔', '深水埗',
                  '觀塘', '天水圍', '油麻地', '長洲', '南丫島', '大澳', '赤柱',
                  '淺水灣', '西貢', '沙田', '荃灣', '馬鞍山', '北角', '港島', '西環',
                  '石澳'],
    'taiwan': ['台灣', '臺灣', '台北', '臺北', '高雄'],
    'japan': ['日本', '東京', '大阪', '京都', '北海道', '沖繩', '富士山'],
    'china': ['北京', '上海', '廣州', '深圳', '西湖', '蘇州', '杭州', '長城'],
    'europe': ['巴黎', '倫敦', '羅馬', '威尼斯', '柏林', '維也納', '布拉格'],
    'americas': ['紐約', '洛杉磯', '三藩市', '多倫多', '溫哥華'],
}


def _classify_region(place_text: str) -> str:
    """Classify a place name into a region."""
    for region, keywords in _REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in place_text or place_text in kw:
                return region
    return 'other'


def detect_places(lyrics: str) -> dict:
    """Find place names via spaCy NER + fallback list.

    Returns dict of region → list of (place, count).
    """
    nlp = _get_nlp()
    found = Counter()

    # Build a set of all known place names for validation
    all_known = set()
    for places in _REGION_KEYWORDS.values():
        all_known.update(places)
    all_known.update(_HK_PLACES_FALLBACK)

    # NER pass – process lyrics in chunks to handle long texts
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]
    batch_size = 10
    for i in range(0, len(lines), batch_size):
        chunk = '\n'.join(lines[i:i + batch_size])
        doc = nlp(chunk)
        for ent in doc.ents:
            if ent.label_ in ('GPE', 'LOC', 'FAC'):
                text = ent.text.strip()
                if len(text) < 2:
                    continue
                # Accept if it's a known place OR classified to a non-'other' region
                region = _classify_region(text)
                if region != 'other' or text in all_known:
                    found[text] += 1

    # Fallback: check HK-specific places that NER might miss
    for place in _HK_PLACES_FALLBACK:
        count = lyrics.count(place)
        if count > 0 and place not in found:
            found[place] = count

    # Also check all known region keywords directly (NER may skip short names)
    for places in _REGION_KEYWORDS.values():
        for place in places:
            count = lyrics.count(place)
            if count > 0 and place not in found:
                found[place] = count

    # Group by region
    by_region = defaultdict(list)
    for place, count in found.items():
        region = _classify_region(place)
        by_region[region].append((place, count))

    return dict(by_region)
