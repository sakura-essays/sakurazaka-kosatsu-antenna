"""Export metadata candidates and apply article-level reviews after reading public pages.

No scraping, body storage or author-wide approval. Validate the whole batch before
writing. Legacy admin approvals remain valid; new reviews record their evidence.
"""
import argparse, datetime as dt, json, urllib.parse
from collect import ROOT, read, write, canonical, date, UTC


def apply_reviews(entries, dry_run=False):
    sources={s['id']:s for s in read(ROOT/'config/sources.json',[])}
    overrides=read(ROOT/'config/overrides.json',{})
    manual=read(ROOT/'config/manual_articles.json',[])
    existing={canonical(a['url']):a for a in read(ROOT/'state/articles.json',[])}
    manual_by_url={canonical(a['url']):a for a in manual}
    rules=read(ROOT/'config/rules.json',{})
    blocked={canonical(u) for u in overrides.get('blocked_urls',[])}
    now=dt.datetime.now(UTC);seen=set()
    for entry in entries:
        u=canonical(entry['url']);sid=entry['author_id'];source=sources.get(sid)
        if u in seen:raise ValueError('Duplicate review URL: '+u)
        seen.add(u)
        if not source or not source.get('enabled') or sid in overrides.get('blocked_authors',[]) or u in blocked:
            raise ValueError('Disabled, blocked or unknown source/article: '+u)
        home=urllib.parse.urlsplit(source['url']);target=urllib.parse.urlsplit(u)
        if home.hostname!=target.hostname or (home.hostname=='note.com' and not target.path.startswith(home.path.rstrip('/')+'/n/')):
            raise ValueError('Article does not belong to source: '+u)
        if entry.get('body_checked') is not True or canonical(entry.get('evidence_url',''))!=u:
            raise ValueError('Public article body must be checked: '+u)
        title=entry['title'].strip();reason=entry.get('reason','').strip()
        if not title or not reason:raise ValueError('Title and editorial reason required')
        raw=entry['published_at']
        pub=date(raw) if 'T' in raw else dt.date.fromisoformat(raw).isoformat()
        if not pub or (dt.datetime.fromisoformat(pub) if 'T' in pub else dt.datetime.combine(dt.date.fromisoformat(pub),dt.time(),UTC))>now:
            raise ValueError('Unconfirmed or future publication date')
        groups=entry.get('groups',[]);cats=entry.get('categories',[])
        if not groups or any(g not in rules['group_rules'] for g in groups):raise ValueError('Confirmed target group required')
        if not cats or any(c not in rules['categories'] for c in cats):raise ValueError('Unknown category')
        prev=existing.get(u) or manual_by_url.get(u)
        if prev and (prev['author_id']!=sid or prev['title']!=title):raise ValueError('Review metadata differs from existing record: '+u)
        if prev and prev.get('published_at'):
            old=prev['published_at']
            # Never silently replace an established publication date.
            old_day=dt.datetime.fromisoformat(old).astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat() if 'T' in old else old
            new_day=dt.datetime.fromisoformat(pub).astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat() if 'T' in pub else pub
            if old_day!=new_day:raise ValueError('Publication date differs from existing record: '+u)
        o=overrides.setdefault('articles',{}).setdefault(u,{})
        if o.get('status') in ('pending','excluded'):
            raise ValueError('Explicit moderation must be resolved separately: '+u)
        o.update(status='published',verified_nonfiction=True,reviewed_title=title,
                 reviewed_at=now.date().isoformat(),review_method='public_article_body',
                 evidence_url=u,reason=reason,groups=groups,categories=cats)
        if u not in existing and u not in manual_by_url:
            item={k:entry[k] for k in ('title','author_id','groups','categories')}
            item.update(url=u,published_at=pub)
            manual.append(item);manual_by_url[u]=item
    if not dry_run:
        write(ROOT/'config/manual_articles.json',manual)
        write(ROOT/'config/overrides.json',overrides)
    return len(seen)


def candidates():
    sources={s['id']:s for s in read(ROOT/'config/sources.json',[])}
    blocked=read(ROOT/'config/overrides.json',{})
    blocked_urls={canonical(u) for u in blocked.get('blocked_urls',[])}
    rows=[]
    for a in read(ROOT/'state/articles.json',[]):
        src=sources.get(a['author_id'],{})
        if (src.get('enabled') and a['author_id'] not in blocked.get('blocked_authors',[])
                and canonical(a['url']) not in blocked_urls and a['status']!='published'):
            # Include excluded metadata: a missed RSS excerpt must be recoverable.
            rows.append({k:a.get(k) for k in ('url','title','author_id','published_at','status','reason','groups','categories')} | {'article_policy':src.get('article_policy','automatic')})
    return sorted(rows,key=lambda a:(a['article_policy']!='review_required',a['status']!='pending',a['url']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',type=str,help='JSON array of metadata reviewed against public article bodies')
    p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    if args.apply:print('Validated article reviews:',apply_reviews(json.load(open(args.apply,encoding='utf-8')),args.dry_run))
    else:print(json.dumps(candidates(),ensure_ascii=False,indent=2))
