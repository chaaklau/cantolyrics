import json
import pandas as pd
import re

with open('data/analysis_results.json', 'r') as f:
    songs = json.load(f)

df = pd.read_csv('data/checked_1986_2025_with_lyrics.csv')
lyrics_map = dict(zip(df['ID'], df['Lyrics']))

love_cues = ['愛', '情', '戀', '吻', '抱', '心', '掛念', '思念', '迷戀', '喜歡', '親離', '分手', '失戀', '伴侶', '情人']

for s in songs:
    # 1. Broaden Love detection - If the combined romantic+heartbreak score is at least 30% of the max theme, or if explicit love cues are very high
    counts = s.get('themes', {}).get('counts', {})
    rl = counts.get('romantic_love', 0)
    hb = counts.get('heartbreak', 0)
    
    # Simple check: does it mention love words a lot?
    lyric = str(lyrics_map.get(s['id'], ''))
    love_word_count = sum(lyric.count(w) for w in love_cues)
    
    # We will compute a bool flag directly in the analysis output or we handle it in dashboard.
    # Let's handle it in dashboard -     # Let's handle it inonditions there.
