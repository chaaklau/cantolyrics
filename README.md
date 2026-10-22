# cantolyrics

Analysis of Cantonese pop lyrics from 1986–2025. The dashboard is served from `docs/`.

Updated 2026-10-22 (HKT): reviewed the TTR interpretation, added a fixed-window MATTR-50 comparison, corrected word tokenization and repetition data, and standardized the region label to **Mainland China**. The dashboard displays its exact build timestamp in Hong Kong time.

## Rebuild the dashboard

Python 3.9+; rebuilding from cached results uses only the standard library:

```sh
python3 pipeline.py --web-only
```

Refresh word diversity and repetition from the CSV while preserving other cached NLP analyses:

```sh
python3 -m pip install -r requirements.txt
python3 pipeline.py --lexical-only
python3 -m unittest discover -s tests
node --test tests/dashboard.test.js
```

Scripts resolve input and output paths relative to the repository and can run from any working directory. A full `python3 pipeline.py` run additionally requires ToJyutping, cantonesedetect, SnowNLP, spaCy with a Chinese model, and the separately supplied `tool/canto-liwc-temp.csv` dictionary, which is not included in this repository.

## Word diversity methodology

Words are segmented with jieba 0.42.1 from CJK characters (U+4E00–U+9FFF) and Latin letters. Latin tokens are case-insensitive; digits, underscores, punctuation and other scripts are excluded. Repeated choruses and lines are retained.

- **Word TTR**: distinct word tokens divided by all word tokens within each song. Group charts show the arithmetic mean of per-song ratios, not the TTR of concatenated songs.
- **MATTR-50**: mean TTR across every overlapping 50-word window within a song, followed by an equal-weight mean across eligible songs in each group. Songs shorter than 50 tokens are excluded from MATTR, not evaluated with a shorter window. Tooltips report each metric's eligible song count.
- Missing/failed measurements and songs without eligible tokens are excluded from chart averages and rankings.

Whole-song TTR falls across the four decades, while mean MATTR-50 rises overall and peaks in 2006–2015. Lyrics also become longer and contain more repeated lines. These descriptive results do not establish a decline in lexical diversity, rare vocabulary or writing quality, nor do they establish a causal explanation. MATTR reduces the length-comparison problem but remains sensitive to tokenization, window size and local repetition.

Reference: Covington & McFall (2010), [Cutting the Gordian Knot: The Moving-Average Type–Token Ratio (MATTR)](https://doi.org/10.1080/09296171003643098).
