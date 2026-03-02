import json

with open('data/analysis_results.json', 'r') as f:
    songs = json.load(f)

c = 0
for s in songs:
    counts = s.get('themes', {}).get('counts', {})
    
    # Recalculate rank by boosting romantic_love and heartbreak artificially or checking logic
    rl = counts.get('romantic_love', 0)
    hb = counts.get('heartbreak', 0)
    
    # Just print the max category size vs love
    m = max(counts.values()) if counts else 0
    if rl + hb > 0 and rl + hb >= m/2:
        c += 1
        
print("Songs where love/heartbreak is at least half of the top theme:", c)
