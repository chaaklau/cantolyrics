"""Refresh word diversity/repetition without rerunning LIWC or other NLP models."""

import json
from pathlib import Path

from analysis.data_loader import load_songs
from analysis.lexical_analysis import find_word_repetition, word_diversity
from run_analysis import compute_yearly_summary

DATA_DIR = Path(__file__).resolve().parent / 'data'


def refresh():
    """Update cached lexical fields and yearly summaries from the source CSV."""
    results_path = DATA_DIR / 'analysis_results.json'
    with results_path.open(encoding='utf-8') as f:
        results = json.load(f)
    songs = {song['ID']: song for song in load_songs()}
    if {result['id'] for result in results} != set(songs):
        raise ValueError('Cached song IDs differ from the CSV; run a full analysis first')

    for result in results:
        lyrics = songs[result['id']]['Lyrics']
        lexical = result.setdefault('lexical', {})
        # Preserve cached LIWC, sentiment, register and phonology results.
        lexical.update(
            {
                key: round(value, 4) if isinstance(value, float) else value
                for key, value in word_diversity(lyrics).items()
            }
        )
        repetition = find_word_repetition(lyrics)
        lexical.setdefault('reduplication', {})['top_repeated_words'] = repetition['top_repeated_words']

    yearly = compute_yearly_summary(results)
    for path, data in [
        (results_path, results),
        (DATA_DIR / 'yearly_summary.json', yearly),
    ]:
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'Refreshed word diversity and repetition for {len(results)} songs')


if __name__ == '__main__':
    refresh()
