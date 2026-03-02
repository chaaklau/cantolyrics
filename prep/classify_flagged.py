#!/usr/bin/env python3
"""Classify flagged google_lyrics.json records."""
import json

with open('google_lyrics.json', 'r', encoding='utf-8') as f:
    records = json.load(f)

by_id = {r['_id']: r for r in records}

# IDs confirmed wrong by inspecting first lines + source
wrong_ids = {
    10007: 'Wrong song (最幸福的人 DJ) from mmcuu.com',
    10020: 'Not lyrics - forum post about album WAV files (hot512)',
    10021: 'Wrong page (Sophie Zelmani) from appleofmyeye',
    10022: 'Not lyrics - Korean manhwa site (hanmanhezi)',
    10023: 'Wikipedia article about TV drama, not song lyrics',
    10034: 'Deezer metadata page, no actual lyrics',
    10041: 'Gossip/blacklist site (wiki.nryjbzm.cc), not lyrics',
    10043: 'Shazam credits page, no lyrics',
    10050: 'Douyin video listing, not lyrics',
    10051: 'Newton wiki about 漩渦, not 男唱女唱',
    10065: 'Shazam song listing, not lyrics',
    10071: 'Shazam metadata, not full lyrics',
    10074: 'Wikipedia page about album, not lyrics',
    10082: 'Shazam page, not lyrics',
    10126: 'Adult site (avsea.online) - completely wrong',
    10128: 'Wrong page (Sophie Zelmani) from appleofmyeye',
    10134: 'Karaoke metadata (song.corp), not lyrics',
    10139: 'Shazam credits only',
    10141: 'Shazam Japanese UI, not lyrics',
    10143: 'Blog essay about the song (190 lines), not lyrics',
    10169: 'Shazam page, not full lyrics',
    10184: 'Esquire article about YouTube 2021, not lyrics',
    10189: 'Wikipedia biography of JACE, not song lyrics',
    10223: 'Wikipedia article about Little Magic, not lyrics text',
    10225: 'Wrong artist (人散曲未終 by 似約, not 姚焯菲)',
    10229: 'Wrong song (Hold You Tight, not 台前幕後)',
    10235: 'Wrong song (第一個迷, not 第一管弦樂團)',
    10253: 'Wrong song (霸氣情歌, not 網戀神仙)',
    10275: 'Esquire magazine article, not lyrics',
}

# Ambiguous - title matches but source is unusual or has extra metadata
check_ids = {
    10006: 'English lyrics (You Lost That Loving Feeling). 誠懇 is a Cantonese cover - wrong language?',
    10016: 'JioSaavn - title matches. Check if lyrics are complete',
    10019: 'appleofmyeye - title matches but has metadata headers',
    10033: 'mulanci - first line is ad-lib, title appears in line 3. Probably OK',
    10036: 'Shazam - only partial lyrics (21 lines)',
    10037: 'appleofmyeye - has metadata but title 痛哭 matches. Probably OK',
    10038: 'gecibook - URL says 也許 but searched 決心. Might be wrong song',
    10039: 'appleofmyeye - metadata but title 未完的小說 matches. Probably OK',
    10142: 'mulanci - 159 lines, may include other songs from album',
    10148: 'lyricspros - URL is artist page, not 孤毒 specifically. Wrong song?',
    10185: 'appleofmyeye - metadata but title 真話的清高 matches. Probably OK',
    10186: 'appleofmyeye - metadata but title 關於愛的碎念 matches. Probably OK',
    10215: 'appleofmyeye - title shown as Distance (English name for 距離). Probably OK',
    10240: 'appleofmyeye - metadata but title 黑玻璃 matches. Probably OK',
    10247: 'lyricspros - title matches. Probably OK',
    10249: 'lyricspros - title matches. Probably OK',
    10251: 'appleofmyeye - metadata but title 魔氈 matches. Probably OK',
    10256: 'mojigeci - title matches. Probably OK',
    10260: 'StreetVoice artist page - may or may not have full lyrics',
}

print("DEFINITELY WRONG - should be removed (28):")
print("=" * 70)
for _id in sorted(wrong_ids):
    r = by_id[_id]
    t = r['title']
    s = r['info']['歌手'][0]
    print(f"  [{_id}] {t} - {s}")
    print(f"    {wrong_ids[_id]}")
    print(f"    {r['url']}")
    print()

print(f"Count: {len(wrong_ids)}")
print()

print("NEEDS MANUAL CHECK (20):")
print("=" * 70)
for _id in sorted(check_ids):
    if _id in by_id:
        r = by_id[_id]
        t = r['title']
        s = r['info']['歌手'][0]
        print(f"  [{_id}] {t} - {s}")
        print(f"    {check_ids[_id]}")
        print(f"    {r['url']}")
        print()

print(f"Count: {len(check_ids)}")
