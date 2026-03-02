#!/usr/bin/env python3
"""
Jyutping conversion and phonological analysis.

- Convert lyrics to Jyutping via ToJyutping
- Analyse tone patterns, tone contours
- Detect large tone jumps (大跳)
"""

import re
from collections import Counter
import ToJyutping


# ── Jyutping helpers ───────────────────────────────────────────────────────

# Jyutping tone → pitch level (approximate, for contour analysis)
# 1=high-level, 2=mid-rising, 3=mid-level, 4=low-falling, 5=low-rising, 6=low-level
TONE_PITCH = {1: 55, 2: 35, 3: 33, 4: 21, 5: 23, 6: 22}

# Pairs considered "large jumps" (黃志華 大跳): tone moving across > 2 pitch levels
# We define jump size as abs difference in starting pitch
TONE_START = {1: 5, 2: 2, 3: 3, 4: 2, 5: 2, 6: 2}
TONE_END   = {1: 5, 2: 5, 3: 3, 4: 1, 5: 3, 6: 2}

# 0243 framework categories (黃志華)
TONE_0243 = {1: '3', 2: '3', 3: '4', 4: '0', 5: '4', 6: '2'}

# Entering tones (入聲): tones 1,3,6 with -p/-t/-k finals
ENTERING_FINALS = re.compile(r'(p|t|k)$')


def lyrics_to_jyutping(text):
    """Convert Chinese text to list of (char, jyutping) pairs.
    Returns list of (char, jyutping_or_None) for each character."""
    result = []
    for char, jp in ToJyutping.get_jyutping_list(text):
        if jp:
            result.append((char, jp))
        elif re.match(r'[\u4e00-\u9fff]', char):
            result.append((char, None))
        # Skip non-CJK characters
    return result


def extract_tone(jp):
    """Extract tone number (1-6) from a Jyutping string."""
    if jp and jp[-1].isdigit():
        return int(jp[-1])
    return None


def extract_final(jp):
    """Extract the final (韻母) from Jyutping, excluding tone."""
    if not jp:
        return None
    # Remove tone digit
    base = jp.rstrip('0123456789')
    # Remove initial consonant(s)
    # Jyutping initials: b,p,m,f,d,t,n,l,g,k,ng,h,gw,kw,w,z,c,s,j
    initials = r'^(ng|gw|kw|[bpmfdtnlgkhwzcsj])?'
    m = re.match(initials, base)
    if m and m.group(0):
        return base[m.end():]
    return base


def extract_nucleus_coda(final):
    """Split final into nucleus (vowel) and coda (ending consonant)."""
    if not final:
        return None, None
    # Codas: -m, -n, -ng, -p, -t, -k, -i, -u
    coda_match = re.search(r'(ng|[mnptkiu])$', final)
    if coda_match:
        coda = coda_match.group(0)
        nucleus = final[:coda_match.start()]
        return nucleus if nucleus else None, coda
    return final, ''


def is_entering_tone(jp):
    """Check if a Jyutping syllable is an entering tone (入聲: -p/-t/-k ending)."""
    if not jp:
        return False
    base = jp.rstrip('0123456789')
    return bool(ENTERING_FINALS.search(base))


def rhyme_key(jp):
    """Get rhyme key for a Jyutping syllable (final without initial, preserving tone)."""
    final = extract_final(jp)
    tone = extract_tone(jp)
    if final and tone:
        return f'{final}{tone}'
    return None


def rhyme_key_no_tone(jp):
    """Get rhyme key ignoring tone (for loose rhyme matching)."""
    return extract_final(jp)


# ── Song-level analysis ───────────────────────────────────────────────────

def analyse_tones(lyrics):
    """Analyse tone distribution in lyrics.
    Returns dict with tone counts and proportions."""
    pairs = lyrics_to_jyutping(lyrics)
    tones = [extract_tone(jp) for _, jp in pairs if extract_tone(jp)]
    if not tones:
        return {'counts': {}, 'total': 0, 'proportions': {}}
    counts = Counter(tones)
    total = len(tones)
    proportions = {t: c / total for t, c in counts.items()}
    return {'counts': dict(counts), 'total': total, 'proportions': proportions}


def analyse_tone_jumps(lyrics):
    """Detect adjacent-syllable tone jumps within lines.
    Returns jump statistics and examples of large jumps."""
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]
    all_jumps = []
    large_jumps = []

    for line in lines:
        pairs = lyrics_to_jyutping(line)
        tones_in_line = [(ch, extract_tone(jp)) for ch, jp in pairs if extract_tone(jp)]
        for i in range(len(tones_in_line) - 1):
            ch1, t1 = tones_in_line[i]
            ch2, t2 = tones_in_line[i + 1]
            jump = abs(TONE_START[t1] - TONE_START[t2])
            all_jumps.append(jump)
            if jump >= 3:  # Large jump threshold
                large_jumps.append({
                    'chars': ch1 + ch2,
                    'tones': f'{t1}->{t2}',
                    'jump': jump,
                    'line': line,
                })

    if not all_jumps:
        return {'avg_jump': 0, 'large_jump_ratio': 0, 'large_jumps': [], 'total_pairs': 0}

    return {
        'avg_jump': sum(all_jumps) / len(all_jumps),
        'large_jump_ratio': len(large_jumps) / len(all_jumps),
        'large_jumps': large_jumps[:10],  # Top examples
        'total_pairs': len(all_jumps),
    }


def analyse_rhyme(lyrics):
    """Analyse end-of-line rhyming patterns.

    For each line, extract the last syllable's rhyme key.
    Count consecutive or nearby lines that share rhyme keys.
    """
    lines = [l.strip() for l in lyrics.split('\n') if l.strip()]
    line_endings = []

    for line in lines:
        pairs = lyrics_to_jyutping(line)
        if pairs:
            last_char, last_jp = pairs[-1]
            if last_jp:
                line_endings.append({
                    'char': last_char,
                    'jp': last_jp,
                    'final': extract_final(last_jp),
                    'tone': extract_tone(last_jp),
                    'entering': is_entering_tone(last_jp),
                    'rhyme_key': rhyme_key_no_tone(last_jp),
                })
            else:
                line_endings.append(None)
        else:
            line_endings.append(None)

    # Count rhyming pairs (consecutive lines sharing finals)
    rhyme_pairs = 0
    total_pairs = 0
    entering_count = 0
    final_counter = Counter()

    for i in range(len(line_endings) - 1):
        if line_endings[i] and line_endings[i + 1]:
            total_pairs += 1
            if line_endings[i]['rhyme_key'] == line_endings[i + 1]['rhyme_key']:
                rhyme_pairs += 1

    for e in line_endings:
        if e:
            if e['entering']:
                entering_count += 1
            if e['rhyme_key']:
                final_counter[e['rhyme_key']] += 1

    total_endings = sum(1 for e in line_endings if e)
    return {
        'rhyme_ratio': rhyme_pairs / total_pairs if total_pairs else 0,
        'entering_ratio': entering_count / total_endings if total_endings else 0,
        'total_line_endings': total_endings,
        'rhyme_pairs': rhyme_pairs,
        'total_pairs': total_pairs,
        'top_finals': final_counter.most_common(10),
        'entering_count': entering_count,
    }


def get_0243_sequence(lyrics):
    """Convert lyrics to 0243 framework sequence (黃志華)."""
    pairs = lyrics_to_jyutping(lyrics)
    result = []
    for ch, jp in pairs:
        t = extract_tone(jp)
        if t:
            result.append(TONE_0243[t])
    return ''.join(result)
