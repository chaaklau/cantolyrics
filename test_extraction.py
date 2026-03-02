import json
import numpy as np

with open('data/analysis_results.json', 'r') as f:
    songs = json.load(f)

periods = {
    '1986-1995': [],
    '1996-2005': [],
    '2006-2015': [],
    '2016-2025': []
}

for s in songs:
    y = s['year']
    if 1986 <= y <= 1995: periods['1986-1995'].append(s)
    elif 1996 <= y <= 2005: periods['1996-2005'].append(s)
    elif 2006 <= y <= 2015: periods['2006-2015'].append(s)
    elif 2016 <= y <= 2025: periods['2016-2025'].append(s)

for p, p_songs in periods.items():
    print(f"{p}: {len(p_songs)}")

