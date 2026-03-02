import json
from analysis.lexical_analysis import find_word_repetition

with open('data/analysis_results.json', 'r') as f:
    songs = json.load(f)

# Also need lyrics
import pandas as pd
df = pd.read_csv('data/checked_1986_2025_with_lyrics.csv')
lyrics_map = dict(zip(df['ID'], df['Lyrics']))

for song in songs:
    lyrics = lyrics_map.get(song['id'], '')
    rep = find_word_repetition(lyrics)
    song['lexical']['reduplication']['top_repeated_words'] = rep.get('top_repeated_words', [])

with open('data/analysis_results.json', 'w') as f:
    json.dump(songs, f, indent=2, ensure_ascii=False)
print("Updated analysis_results.json")
