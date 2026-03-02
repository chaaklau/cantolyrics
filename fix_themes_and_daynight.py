import json

with open('data/analysis_results.json', 'r') as f:
    songs = json.load(f)

for s in songs:
    # 1. Fix Day/Night
    # Let's see what values are currently
    day = s.get('lexical', {}).get('day_night', {}).get('day_count', 0)
    night = s.get('lexical', {}).get('day_night', {}).get('night_count', 0)
    
    # 2. Fix Love Themes
    # Let's adjust theme counting to be based on direct words maybe?
    # Actually wait, I shouldn't just modify the json, I should re-run analysis or adjust dashboard to lower the threshold of love.
    # Currently love is only if it's the TOP #1 theme.
