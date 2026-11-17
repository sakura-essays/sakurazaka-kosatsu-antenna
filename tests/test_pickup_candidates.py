import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('pickup_candidates', pathlib.Path(__file__).parents[1] / 'scripts/pickup_candidates.py')
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 11, 17)
        self.rows = [dict(url=f'https://example.com/{i}', author_id=f'author{i % 12}',
                          published_at='2023-01-01', groups=['櫻坂46'],
                          categories=['楽曲・歌詞考察']) for i in range(80)]

    def test_unread_cooldown_and_recheck(self):
        ledger = {'observations': [dict(url=self.rows[0]['url'], full_text_read=True),
                                  dict(url=self.rows[1]['url'], full_text_read=True, recheck_needed=True),
                                  dict(url=self.rows[2]['url'], full_text_obtained=True)]}
        events = [dict(published_at='2026-10-01T00:00:00+09:00', urls=[self.rows[4]['url']]),
                  dict(published_at='2026-10-10T00:00:00+09:00', urls=[]),
                  dict(published_at='2026-10-21T00:00:00+09:00', urls=[self.rows[3]['url']])]
        result = pc.extract(self.rows, ledger, events, self.today, 'test', 80)
        urls = {r['url'] for r in result['candidates']}
        self.assertNotIn(self.rows[0]['url'], urls)
        self.assertNotIn(self.rows[3]['url'], urls)
        for i in [1, 2, 4]:
            self.assertIn(self.rows[i]['url'], urls)

    def test_latest_recheck_overrides_an_earlier_read(self):
        ledger = {'observations': [dict(url=self.rows[0]['url'], full_text_read=True),
                                  dict(url=self.rows[0]['url'], full_text_read=True, recheck_needed=True)]}
        result = pc.extract(self.rows, ledger, [], self.today, 'x', 80)
        self.assertIn(self.rows[0]['url'], {x['url'] for x in result['candidates']})

    def test_reproducible_unique_and_random(self):
        a = pc.extract(self.rows, {}, [], self.today, 'week1')
        b = pc.extract(self.rows, {}, [], self.today, 'week1')
        c = pc.extract(self.rows, {}, [], self.today, 'week2')
        self.assertEqual(a, b)
        self.assertNotEqual(a['candidates'], c['candidates'])
        self.assertEqual(30, len({x['url'] for x in a['candidates']}))
        self.assertEqual(6, sum(x['discovery_method'] == 'random' for x in a['candidates']))
        self.assertGreaterEqual(len({x['author_id'] for x in a['candidates']}), 10)

    def test_small_pool_and_missing_dates(self):
        self.assertEqual([], pc.extract([], {}, [], self.today, 'x')['candidates'])
        self.assertEqual('unknown', pc.age_bucket({}, self.today))
        self.assertEqual('7d', pc.age_bucket({'published_at': '2026-11-16'}, self.today))
        self.assertEqual('8-30d', pc.age_bucket({'published_at': '2026-10-20'}, self.today))
        self.assertEqual('31-89d', pc.age_bucket({'published_at': '2026-09-20'}, self.today))

    def test_unchanged_pickup_is_still_recent(self):
        events = [dict(published_at='2025-01-01T00:00:00+09:00', urls=[self.rows[0]['url']])]
        result = pc.extract(self.rows, {}, events, self.today, 'x', 80)
        self.assertNotIn(self.rows[0]['url'], {x['url'] for x in result['candidates']})

    def test_public_state_source_and_override_must_all_allow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            files = {'dist/data/articles.json': self.rows[:6],
                     'state/articles.json': [dict(a, status='held' if i == 1 else 'published') for i, a in enumerate(self.rows[:6])],
                     'config/sources.json': [dict(id=f'author{i}', enabled=i != 2) for i in range(6)],
                     'config/overrides.json': {'blocked_authors': ['author3'], 'blocked_urls': [self.rows[5]['url']], 'articles': {self.rows[4]['url']: {'status': 'excluded'}}}}
            for path, value in files.items():
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(json.dumps(value))
            self.assertEqual([self.rows[0]], pc.eligible(root))
