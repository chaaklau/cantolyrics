import json
import os
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')

def format_region(r):
    m = {
        'chinese_mainland': 'Chinese Mainland',
        'china': 'Chinese Mainland',
        'taiwan': 'Taiwan',
        'japan': 'Japan',
        'europe': 'Europe',
        'hong_kong': 'Hong Kong',
        'macau': 'Macau',
        'north_america': 'North America',
        'southeast_asia': 'Southeast Asia'
    }
    return m.get(r, r.replace('_', ' ').title())

def load_data():
    with open(os.path.join(DATA_DIR, 'analysis_results.json'), 'r', encoding='utf-8') as f:
        songs = json.load(f)
        
    csv_path = os.path.join(DATA_DIR, 'checked_1986_2025_with_lyrics.csv')
    df = pd.read_csv(csv_path)
    lyrics_dict = dict(zip(df['ID'].astype(str), df['Lyrics'].fillna('')))
    
    return songs, lyrics_dict

def run():
    songs, lyrics_dict = load_data()
        
    # 1. Descriptive Stats
    singers = {}
    lyricists = {}
    years = set()
    for s in songs:
        singer = s.get('singer', 'Unknown')
        lyricist = s.get('lyricist', 'Unknown')
        singers[singer] = singers.get(singer, 0) + 1
        lyricists[lyricist] = lyricists.get(lyricist, 0) + 1
        if s.get('year'): years.add(s.get('year'))
        
    top_singers = [{'name': k, 'count': v} for k, v in sorted(singers.items(), key=lambda x: -x[1])]
    top_lyricists = [{'name': k, 'count': v} for k, v in sorted(lyricists.items(), key=lambda x: -x[1])]
    
    global_stats = {
        'total_songs': len(songs),
        'top_singer': f"{top_singers[0]['name']} ({top_singers[0]['count']})" if top_singers else "N/A",
        'top_lyricist': f"{top_lyricists[0]['name']} ({top_lyricists[0]['count']})" if top_lyricists else "N/A",
        'years_covered': f"{min(years)} - {max(years)}" if years else "N/A",
    }
    
    # 2. Extract Global Top 15 Rhymes (based on MOST FREQUENT rhyme per song, not generic occurrences)
    rhyme_totals = {}
    for s in songs:
        finals = s.get('rhyme', {}).get('top_finals', [])
        if finals:
            best_rhyme = finals[0][0]
            rhyme_totals[best_rhyme] = rhyme_totals.get(best_rhyme, 0) + 1
    top_rhymes_keys = [k for k, v in sorted(rhyme_totals.items(), key=lambda x: -x[1])[:15]]
    
    # 3. Extract Regions
    all_regions_set = set()
    for s in songs:
        for r in s.get('places', {}).keys():
            all_regions_set.add(format_region(r))
    all_regions = sorted(list(all_regions_set))
            
    # Compile song database for frontend Top/Bottom interactions
    song_db = []
    
    # Groupings
    periods_10 = {'1986-<br>1995': [], '1996-<br>2005': [], '2006-<br>2015': [], '2016-<br>2025': []}
    periods_5 = {
        '1986-<br>1990': [], '1991-<br>1995': [], '1996-<br>2000': [], '2001-<br>2005': [],
        '2006-<br>2010': [], '2011-<br>2015': [], '2016-<br>2020': [], '2021-<br>2025': []
    }
    yearly = {y: [] for y in range(1986, 2026)}
    
    for s in songs:
        y = s.get('year')
        if not y: continue
        
        th = s.get('themes', {})
        counts = th.get('counts', {})
        rl, hb = counts.get('romantic_love', 0), counts.get('heartbreak', 0)
        m = max(counts.values()) if counts and counts.values() else 0
        is_love = th.get('primary', '') in ['romantic_love', 'heartbreak'] or (rl + hb >= max(1, m * 0.4))
        
        rep_dict = s.get('lexical', {}).get('reduplication', {})
        raw_rep = len(rep_dict.get('top_repeated_words', [])) + rep_dict.get('char_redup_types', 0)
        
        song_db.append({
            'id': s['id'],
            'title': s['title'],
            'singer': s['singer'],
            'year': s['year'],
            'metrics': {
                'jump': s.get('tone_jumps', {}).get('large_jump_ratio', 0),
                'rhyme': s.get('rhyme', {}).get('rhyme_ratio', 0),
                'repeated': raw_rep,
                'ttr': s.get('lexical', {}).get('word_ttr', 0),
                'cantonese': s.get('register', {}).get('counts', {}).get('cantonese', 0),
                'english': s.get('lexical', {}).get('english_word_count', 0),
                'sentiment': s.get('sentiment', {}).get('score', 0),
                'day': s.get('lexical', {}).get('day_night', {}).get('day_count', 0),
                'night': s.get('lexical', {}).get('day_night', {}).get('night_count', 0),
                'places': sum(1 for p in s.get('places', {}).keys())
            },
            'is_love': is_love,
            'top_finals': [f for f, c in s.get('rhyme', {}).get('top_finals', [])],
            'lyrics': lyrics_dict.get(s['id'], 'No lyrics found.')
        })
        
        if 1986 <= y <= 1995: periods_10['1986-<br>1995'].append(s)
        elif 1996 <= y <= 2005: periods_10['1996-<br>2005'].append(s)
        elif 2006 <= y <= 2015: periods_10['2006-<br>2015'].append(s)
        elif 2016 <= y <= 2025: periods_10['2016-<br>2025'].append(s)
        
        if 1986 <= y <= 1990: periods_5['1986-<br>1990'].append(s)
        elif 1991 <= y <= 1995: periods_5['1991-<br>1995'].append(s)
        elif 1996 <= y <= 2000: periods_5['1996-<br>2000'].append(s)
        elif 2001 <= y <= 2005: periods_5['2001-<br>2005'].append(s)
        elif 2006 <= y <= 2010: periods_5['2006-<br>2010'].append(s)
        elif 2011 <= y <= 2015: periods_5['2011-<br>2015'].append(s)
        elif 2016 <= y <= 2020: periods_5['2016-<br>2020'].append(s)
        elif 2021 <= y <= 2025: periods_5['2021-<br>2025'].append(s)
        
        if y in yearly: yearly[y].append(s)
        
    labels_10 = list(periods_10.keys())
    labels_5 = list(periods_5.keys())
    labels_yearly = sorted(list(yearly.keys()))
    
    def calc_stats(groups_dict, labels):
        stats = {
            'total_songs': [],
            'high_jump': [], 'clear_rhyme': [], 'repeated_words': [],
            'cantonese_alot': [], 'cantonese': [], 'neutral_swc': [], 'ttr': [],
            'day': [], 'night': [], 'not_clear': [],
            'love': [], 'other': [],
            'sentiment_mean': [], 'sentiment_std': [],
            'place': [], 'english': [],
            'rhymes': {r: [] for r in top_rhymes_keys},
            'places_counts': {r: [] for r in all_regions},
            'top_songs': {
                'high_jump': [], 'clear_rhyme': [], 'repeated_words': [], 'cantonese_alot': [], 
                'english': [], 'place': [], 'day': [], 'night': [], 'love': [], 'not_clear': [], 'cantonese': [], 'neutral_swc': [], 'other': []
            } # to store html string for top 5 songs
        }
        
        def get_top_html(songs_list, sort_key=None, reverse=True):
            if sort_key:
                sorted_songs = sorted(songs_list, key=sort_key, reverse=reverse)[:5]
            else:
                sorted_songs = songs_list[:5]
            return "<br>" + "<br>".join([f"- {s['title']} ({s['singer']})" for s in sorted_songs]) if sorted_songs else ""

        for p in labels:
            pset = groups_dict.get(p, [])
            total = len(pset)
            stats['total_songs'].append(total)
            if total == 0:
                for k in stats: 
                    if isinstance(stats[k], list) and k != 'total_songs': stats[k].append(0)
                    elif isinstance(stats[k], dict) and k == 'top_songs':
                        for sub_k in stats[k]: stats[k][sub_k].append("")
                for r in top_rhymes_keys: stats['rhymes'][r].append(0)
                for pl in all_regions: stats['places_counts'][pl].append(0)
                continue
                
            jump_songs = [s for s in pset if s.get('tone_jumps', {}).get('large_jump_ratio', 0) >= 0.3]
            stats['high_jump'].append(len(jump_songs) / total * 100)
            stats['top_songs']['high_jump'].append(get_top_html(jump_songs, lambda x: x.get('tone_jumps', {}).get('large_jump_ratio', 0)))

            rhyme_songs = [s for s in pset if s.get('rhyme', {}).get('rhyme_ratio', 0) >= 0.5]
            stats['clear_rhyme'].append(len(rhyme_songs) / total * 100)
            stats['top_songs']['clear_rhyme'].append(get_top_html(rhyme_songs, lambda x: x.get('rhyme', {}).get('rhyme_ratio', 0)))
            
            repeated_songs = []
            for s in pset:
                rep = s.get('lexical', {}).get('reduplication', {})
                if len(rep.get('top_repeated_words', [])) >= 3 or rep.get('char_redup_types', 0) >= 3:
                    repeated_songs.append(s)
            stats['repeated_words'].append(len(repeated_songs) / total * 100)
            stats['top_songs']['repeated_words'].append(get_top_html(repeated_songs, lambda x: len(x.get('lexical', {}).get('reduplication', {}).get('top_repeated_words', [])) + x.get('lexical', {}).get('reduplication', {}).get('char_redup_types', 0)))
            
            c_alot_songs, c_some_songs, neutral_songs = [], [], []
            for s in pset:
                cnt = s.get('register', {}).get('counts', {}).get('cantonese', 0)
                if cnt >= 3: c_alot_songs.append(s)
                elif cnt >= 1: c_some_songs.append(s)
                else: neutral_songs.append(s)
            stats['cantonese_alot'].append(len(c_alot_songs) / total * 100)
            stats['cantonese'].append(len(c_some_songs) / total * 100)
            stats['neutral_swc'].append(len(neutral_songs) / total * 100)
            stats['top_songs']['cantonese_alot'].append(get_top_html(c_alot_songs, lambda x: x.get('register', {}).get('counts', {}).get('cantonese', 0)))
            stats['top_songs']['cantonese'].append(get_top_html(c_some_songs, lambda x: x.get('register', {}).get('counts', {}).get('cantonese', 0)))
            stats['top_songs']['neutral_swc'].append(get_top_html(neutral_songs))
            
            ttrs = [s.get('lexical', {}).get('word_ttr', 0) for s in pset]
            stats['ttr'].append(float(np.mean(ttrs)) if ttrs else 0)
            
            d_songs, n_songs, nc_songs = [], [], []
            for s in pset:
                dn = s.get('lexical', {}).get('day_night', {})
                d, n = dn.get('day_count', 0), dn.get('night_count', 0)
                if d == 0 and n == 0: nc_songs.append(s)
                elif d > n: d_songs.append(s)
                elif n > d: n_songs.append(s)
                else: nc_songs.append(s)
            stats['day'].append(len(d_songs) / total * 100)
            stats['night'].append(len(n_songs) / total * 100)
            stats['not_clear'].append(len(nc_songs) / total * 100)
            stats['top_songs']['day'].append(get_top_html(d_songs, lambda x: x.get('lexical', {}).get('day_night', {}).get('day_count', 0)))
            stats['top_songs']['night'].append(get_top_html(n_songs, lambda x: x.get('lexical', {}).get('day_night', {}).get('night_count', 0)))
            stats['top_songs']['not_clear'].append(get_top_html(nc_songs))

            love_songs, other_songs = [], []
            for s in pset:
                th = s.get('themes', {})
                counts = th.get('counts', {})
                rl, hb = counts.get('romantic_love', 0), counts.get('heartbreak', 0)
                m = max(counts.values()) if counts and counts.values() else 0
                pr = th.get('primary', '')
                if pr in ['romantic_love', 'heartbreak'] or (rl + hb >= max(1, m * 0.4)):
                    love_songs.append(s)
                else:
                    other_songs.append(s)
            stats['love'].append(len(love_songs) / total * 100)
            stats['other'].append(len(other_songs) / total * 100)
            stats['top_songs']['love'].append(get_top_html(love_songs))
            stats['top_songs']['other'].append(get_top_html(other_songs))
            
            sents = [s.get('sentiment', {}).get('score', 0) for s in pset]
            stats['sentiment_mean'].append(float(np.mean(sents)) if sents else 0)
            stats['sentiment_std'].append(float(np.std(sents)) if sents else 0)
            
            place_songs = [s for s in pset if len(s.get('places', {}).keys()) > 0]
            english_songs = [s for s in pset if s.get('lexical', {}).get('english_word_count', 0) > 0]
            stats['place'].append(len(place_songs) / total * 100)
            stats['english'].append(len(english_songs) / total * 100)
            stats['top_songs']['place'].append(get_top_html(place_songs, lambda x: sum(1 for p in x.get('places', {}).keys())))
            stats['top_songs']['english'].append(get_top_html(english_songs, lambda x: x.get('lexical', {}).get('english_word_count', 0)))
            
            # Rhymes per period (count how many songs used this rhyme as their MOST FREQUENT rhyme)
            r_counts = {r: 0 for r in top_rhymes_keys}
            for s in pset:
                finals = s.get('rhyme', {}).get('top_finals', [])
                if finals:
                    best_rhyme = finals[0][0]
                    if best_rhyme in r_counts:
                        r_counts[best_rhyme] += 1
            for r in r_counts: stats['rhymes'][r].append(r_counts[r])
            
            # Places absolute counts per period grouped by Region
            # (Counting NUMBER OF SONGS that contain a place in that region, not raw mentions)
            p_counts = {pl: 0 for pl in all_regions}
            for s in pset:
                # keep track of which regions this song has already been counted for
                counted_regions_for_song = set()
                for r, p_list in s.get('places', {}).items():
                    fmt_r = format_region(r)
                    if not p_list: continue # Just in case it's an empty list
                    
                    if fmt_r not in counted_regions_for_song:
                        p_counts[fmt_r] += 1
                        counted_regions_for_song.add(fmt_r)
                        
            for pl in p_counts: stats['places_counts'][pl].append(p_counts[pl])
            
        return stats
        
    dashboard_data = {
        'global_stats': global_stats,
        'labels_10': labels_10,
        'labels_5': labels_5,
        'labels_yearly': labels_yearly,
        'stats_10': calc_stats(periods_10, labels_10),
        'stats_5': calc_stats(periods_5, labels_5),
        'stats_yearly': calc_stats(yearly, labels_yearly),
        'all_places': all_regions,
        'top_rhymes': top_rhymes_keys,
        'songs': song_db
    }
    
    os.makedirs('web', exist_ok=True)
    
    with open('web/data.js', 'w', encoding='utf-8') as f:
        f.write('const DB_DATA = ')
        json.dump(dashboard_data, f, ensure_ascii=False)
        f.write(';')
        
    with open('dashboard_template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    
    with open('web/index.html', 'w', encoding='utf-8') as f:
        f.write(template)
        
    print(f"Dashboard generated at web/index.html")

if __name__ == '__main__':
    run()