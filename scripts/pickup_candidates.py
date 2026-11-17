"""Discovery metadata only. This script never reads, scores or selects essays."""
import argparse
import collections
import datetime as dt
import json
import pathlib
import random
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def history(root):
    """All actual setting changes, including initial publication, oldest first."""
    commits = subprocess.check_output(
        ['git', '-C', str(root), 'log', '--reverse', '--format=%H',
         'HEAD', '--', 'config/pickups.json'], text=True).splitlines()
    events = []
    for commit in commits:
        rows = json.loads(subprocess.check_output(
            ['git', '-C', str(root), 'show', commit + ':config/pickups.json'], text=True))
        if not rows:
            continue
        timestamp = subprocess.check_output(
            ['git', '-C', str(root), 'show', '-s', '--format=%cI', commit], text=True).strip()
        events.append({'commit': commit, 'published_at': timestamp,
                       'urls': [row['url'] for row in rows]})
    return events


def eligible(root):
    public = read(root / 'dist/data/articles.json', [])
    state = {a['url']: a for a in read(root / 'state/articles.json', [])}
    overrides = read(root / 'config/overrides.json', {})
    blocked = set(overrides.get('blocked_authors', []))
    blocked_urls = set(overrides.get('blocked_urls', []))
    enabled = {s['id'] for s in read(root / 'config/sources.json', [])
               if s.get('enabled') and s['id'] not in blocked}
    result = []
    for a in public:
        override = overrides.get('articles', {}).get(a['url'], {})
        if (a['url'] not in blocked_urls and a['author_id'] in enabled
                and state.get(a['url'], {}).get('status') == 'published'
                and override.get('status', 'published') == 'published'):
            result.append(a)
    return result


def age_bucket(article, today):
    try:
        days = (today - dt.date.fromisoformat(article['published_at'][:10])).days
    except (ValueError, KeyError, TypeError):
        return 'unknown'
    if days <= 7:
        return '7d'
    if days <= 30:
        return '8-30d'
    if days < 90:
        return '31-89d'
    return '90d+'


def extract(articles, ledger, events, today, seed, count=30):
    latest = {r['url']: r for r in ledger.get('observations', [])}
    reviewed = {r['url'] for r in latest.values()
                if r.get('full_text_read') and not r.get('recheck_needed')}
    # Acquisition alone is not proof of reading. Previous candidates remain eligible.
    cutoff = today - dt.timedelta(days=28)
    recent = set()
    ordered = sorted(events, key=lambda e: e['published_at'])
    for index, event in enumerate(ordered):
        start = dt.datetime.fromisoformat(event['published_at']).date()
        end = (dt.datetime.fromisoformat(ordered[index + 1]['published_at']).date()
               if index + 1 < len(ordered) else today)
        # A setting still displayed this month is recent even if committed months ago.
        if start <= today and end >= cutoff:
            recent.update(event['urls'])
    pool = [a for a in articles if a['url'] not in reviewed and a['url'] not in recent]
    rng = random.Random(seed)
    pool.sort(key=lambda a: a['url'])
    rng.shuffle(pool)
    chosen = []
    authors, groups, ages, categories = (collections.Counter() for _ in range(4))

    def take(a, method):
        chosen.append(dict(a, discovery_method=method, age_bucket=age_bucket(a, today)))
        authors[a['author_id']] += 1
        groups.update(a.get('groups') or ['unclassified'])
        ages[age_bucket(a, today)] += 1
        categories.update(a.get('categories') or ['unclassified'])
        pool.remove(a)

    # One fifth is a genuine random draw without title/author/popularity weighting.
    for a in list(pool[:min(6, count)]):
        take(a, 'random')
    while pool and len(chosen) < count:
        # This only distributes opportunities for reading, never estimates quality.
        def coverage(a):
            return (6 / (1 + authors[a['author_id']])
                    + 3 / (1 + ages[age_bucket(a, today)])
                    + sum(2 / (1 + groups[g]) for g in a.get('groups', []))
                    + sum(1 / (1 + categories[c]) for c in a.get('categories', [])))
        take(max(pool, key=coverage), 'coverage')
    return {'as_of': today.isoformat(), 'seed': seed,
            'eligible_count': len(articles), 'unread_available_count': len(pool) + len(chosen),
            'previously_featured_urls': sorted({u for e in events for u in e['urls']}),
            'cooldown_urls': sorted(recent), 'history': events, 'candidates': chosen}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date', default=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat())
    p.add_argument('--seed')
    p.add_argument('--count', type=int, default=30)
    p.add_argument('--output', type=pathlib.Path, required=True)
    args = p.parse_args()
    if not 1 <= args.count <= 100:
        p.error('--count must be 1..100')
    today = dt.date.fromisoformat(args.date)
    data = extract(eligible(ROOT), read(ROOT / 'state/pickup_discovery.json', {}),
                   history(ROOT), today, args.seed or args.date, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in data.items() if k.endswith('_count')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
