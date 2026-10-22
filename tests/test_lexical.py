import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_dashboard
import refresh_lexical
from analysis.lexical_analysis import moving_average_ttr, segment_words, word_diversity


class DiversityTests(unittest.TestCase):
    def test_case_and_nonword_tokens(self):
        self.assertEqual(segment_words('Love LOVE love! 123 ___ ♥'), ['love'] * 3)
        stats = word_diversity('Love LOVE love! 123 ___ ♥')
        self.assertEqual(stats['total_words'], 3)
        self.assertEqual(stats['unique_words'], 1)
        self.assertAlmostEqual(stats['word_ttr'], 1 / 3)
        self.assertIsNone(stats['word_mattr_50'])

    def test_empty_text(self):
        for text in ['', '123 ___!?', '♪♫']:
            with self.subTest(text=text):
                self.assertEqual(word_diversity(text)['total_words'], 0)
                self.assertEqual(word_diversity(text)['word_ttr'], 0)
                self.assertIsNone(word_diversity(text)['word_mattr_50'])

    def test_cjk_and_latin(self):
        self.assertEqual(segment_words('日 月 日 LOVE'), ['日', '月', '日', 'love'])

    def test_mattr_uses_every_overlapping_window(self):
        # aab -> 2/3, aba -> 2/3, bac -> 3/3
        self.assertAlmostEqual(moving_average_ttr(list('aabac'), 3), 7 / 9)

    def test_mattr_repeated_words_enter_and_leave(self):
        # abc -> 1, bca -> 1, caa -> 2/3, aab -> 2/3
        self.assertAlmostEqual(moving_average_ttr(list('abcaab'), 3), 5 / 6)

    def test_window_boundaries(self):
        self.assertIsNone(moving_average_ttr(['a'] * 49))
        self.assertEqual(moving_average_ttr(['a'] * 50), 1 / 50)
        self.assertEqual(moving_average_ttr(list(range(50))), 1)
        self.assertEqual(moving_average_ttr(list('abca'), 1), 1)
        with self.assertRaises(ValueError):
            moving_average_ttr([], 0)

    def test_repeating_a_passage_changes_whole_song_ttr(self):
        original = 'love moon night day sun '
        self.assertEqual(word_diversity(original)['word_ttr'], 1)
        self.assertEqual(word_diversity(original * 2)['word_ttr'], 0.5)


class DashboardTests(unittest.TestCase):
    def test_mainland_aliases(self):
        for region in ['china', 'chinese_mainland', 'mainland_china']:
            self.assertEqual(build_dashboard.format_region(region), 'Mainland China')

    def test_missing_invalid_and_empty_measurements(self):
        for lexical in [
            {},
            {'error': 'failed'},
            {'word_ttr': None},
            {'word_ttr': float('nan')},
            {'word_ttr': float('inf')},
            {'word_ttr': -1},
            {'word_ttr': 2},
            {'word_ttr': True},
            {'word_ttr': 0, 'total_words': 0},
        ]:
            with self.subTest(lexical=lexical):
                self.assertIsNone(build_dashboard.diversity_value({'lexical': lexical}, 'word_ttr'))

    def test_group_means_exclude_missing_values(self):
        songs = [
            {
                'id': 'a',
                'year': 1986,
                'title': '<a>',
                'singer': 'Singer',
                'lyricist': 'A',
                'lexical': {'total_words': 100, 'word_ttr': 0.5, 'word_mattr_50': 0.8},
                'places': {'china': [['北京', 1]], 'chinese_mainland': [['上海', 1]]},
            },
            {
                'id': 'b',
                'year': 1986,
                'title': 'B',
                'singer': 'Singer',
                'lyricist': 'B',
                'lexical': {'total_words': 20, 'word_ttr': 1, 'word_mattr_50': None},
            },
            {
                'id': 'c',
                'year': 1986,
                'title': 'C',
                'singer': 'Singer',
                'lyricist': 'C',
                'lexical': {'error': 'failed'},
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / 'docs'
            with (
                patch.object(build_dashboard, 'load_data', return_value=(songs, {})),
                patch.object(build_dashboard, 'DOCS_DIR', docs),
            ):
                build_dashboard.run()
            data = json.loads((docs / 'data.js').read_text()[len('const DB_DATA = ') : -1])
            stats = data['stats_10']
            self.assertEqual(stats['ttr'], [0.75, None, None, None])
            self.assertEqual(stats['mattr_50'], [0.8, None, None, None])
            self.assertEqual(stats['ttr_song_count'], [2, 0, 0, 0])
            self.assertEqual(stats['mattr_50_song_count'], [1, 0, 0, 0])
            self.assertEqual(stats['places_counts']['Mainland China'], [1, 0, 0, 0])
            page = (docs / 'index.html').read_text()
            self.assertNotIn('{{ ', page)
            self.assertIn('HKT (UTC+08:00)', page)
            self.assertIn(data['updated_at'], page)

    def test_lexical_refresh_preserves_other_analysis(self):
        result = {
            'id': 'a',
            'year': 1986,
            'title': 'A',
            'singer': 'S',
            'lyricist': 'L',
            'gender': 'U',
            'singer_type': 'unknown',
            'sentiment': {'score': 0.5},
            'lexical': {'liwc': {'normalised': {'love': 0.25}}, 'reduplication': {}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'analysis_results.json'
            path.write_text(json.dumps([result]))
            with (
                patch.object(refresh_lexical, 'DATA_DIR', Path(tmp)),
                patch.object(
                    refresh_lexical,
                    'load_songs',
                    return_value=[{'ID': 'a', 'Lyrics': 'LOVE love love'}],
                ),
            ):
                refresh_lexical.refresh()
            refreshed = json.loads(path.read_text())[0]
            self.assertEqual(refreshed['sentiment'], result['sentiment'])
            self.assertEqual(refreshed['lexical']['liwc'], result['lexical']['liwc'])
            self.assertEqual(refreshed['lexical']['total_words'], 3)
            self.assertEqual(
                refreshed['lexical']['reduplication']['top_repeated_words'],
                [['love', 3]],
            )


if __name__ == '__main__':
    unittest.main()
