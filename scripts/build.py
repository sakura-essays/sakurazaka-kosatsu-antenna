"""Publish metadata only; never copy review queues/feed bodies to dist."""
import collections,hashlib,html,json,os,pathlib,re,shutil,urllib.parse
from collect import ROOT,read,write,detect_groups,GROUP_ORDER,song_match,norm,normalize_categories

def sync_github_owner(settings):
 """Keep Pages and Issue URLs valid after a GitHub account rename."""
 slug=os.environ.get('GITHUB_REPOSITORY','')
 m=re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+)',slug)
 if not m:return
 owner,name=m.groups()
 old_repo=settings.get('repository_url','')
 new_repo=f'https://github.com/{owner}/{name}'
 # Only update links that still target this very repository.
 if old_repo==new_repo or not old_repo.startswith('https://github.com/') or not old_repo.endswith('/'+name):return
 old_contact=settings.get('contact_url','')
 if old_contact.startswith(old_repo+'/issues/'):
  settings['contact_url']=new_repo+old_contact[len(old_repo):]
 old_base=settings.get('base_url','')
 if re.fullmatch(r'https://[A-Za-z0-9-]+\.github\.io/'+re.escape(name)+r'/?',old_base):
  settings['base_url']=f'https://{owner}.github.io/{name}'
 settings['repository_url']=new_repo
 write(ROOT/'config/settings.json',settings)

def curated_pickups(articles, selections):
 """Return public, manually vetted picks only; never publish internal ratings."""
 if not isinstance(selections,list):raise ValueError('config/pickups.json must be an array')
 available={a['url'] for a in articles}
 seen=set();chosen=[]
 for entry in selections:
  if not isinstance(entry,dict):raise ValueError('Each pick must be a JSON object')
  url=entry.get('url','')
  note=entry.get('note','')
  if not isinstance(url,str) or not url.startswith('https://'):
   raise ValueError('Pickup URL must be HTTPS')
  if not isinstance(note,str) or not (1<=len(note.strip())<=160):
   raise ValueError('Pickup note must be 1–160 characters')
  if url in seen:continue
  seen.add(url)
  # A removed, held or blocked article must never reappear via the feature.
  if url not in available:continue
  chosen.append({'url':url,'note':note.strip()})
  if len(chosen)>=6:break
 return chosen


def song_index_content(articles, sources, rules):
 """Static, title-led song links for humans and crawlers; no popularity ranking."""
 writers={s['id']:s['name'] for s in sources if s.get('enabled')}
 sections=[]
 for group in GROUP_ORDER:
  song_names=rules.get('group_rules',{}).get(group,{}).get('songs',[])
  song_blocks=[]
  seen_songs=set()
  for song in song_names:
   if norm(song) in seen_songs:continue
   seen_songs.add(norm(song))
   matches=[a for a in articles if group in a.get('groups',[])
            and song_match(song,norm(a.get('title','')))]
   if not matches:continue
   # The original article title and its author are kept, without engagement data.
   matches.sort(key=lambda a:(a.get('published_at') or '',a['url']),reverse=True)
   anchor='song-'+hashlib.sha256((group+'\\0'+song).encode()).hexdigest()[:12]
   rows=[]
   for a in matches:
    href=html.escape(a['url'],quote=True)
    title=html.escape(a['title'])
    author=html.escape(writers.get(a['author_id'],a['author_id']))
    rows.append('<li><a class="tracked-article" data-placement="song_index" data-article-id="'+html.escape(a['id'],quote=True)+'" data-author-id="'+html.escape(a['author_id'],quote=True)+'" data-author-name="'+html.escape(writers.get(a['author_id'],a['author_id']),quote=True)+'" data-article-group="'+html.escape(' / '.join(a.get('groups',[])),quote=True)+'" href="'+href+'" rel="external">'+title+'</a><span class="song-author">— '+author+'</span></li>')
   song_blocks.append('<section class="song-block" id="'+anchor+'"><h3>'+html.escape(song)+
                      ' <span class="song-count">('+str(len(matches))+'記事)</span></h3><ul class="song-links">'+''.join(rows)+'</ul></section>')
  if song_blocks:
   sections.append('<section class="song-group" aria-label="'+html.escape(group,quote=True)+'"><h2>'+
                   html.escape(group)+'</h2>'+''.join(song_blocks)+'</section>')
 return ''.join(sections) if sections else '<p>現在、楽曲名が記事タイトルに含まれる収録記事はありません。</p>'

def build(public=False):
 settings=read(ROOT/'config/settings.json',{})
 if public:
  sync_github_owner(settings)
  if not settings.get('contact_url','').startswith('https://'):raise ValueError('一般公開前に config/settings.json の contact_url を設定してください')
  if not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',settings.get('repository_url','')):raise ValueError('repository_url を設定してください')
  settings['public_release']=True
 articles=[a for a in read(ROOT/'state/articles.json',[]) if a['status']=='published']
 rules=read(ROOT/'config/rules.json',{})
 for a in articles:
  a['categories']=normalize_categories(a.get('categories',[]))
  if not a.get('groups') and '制作者・クリエイター論' in a.get('categories',[]):
   a['groups']=[]
  else:
   a['groups']=a.get('groups') or detect_groups(a['title'],'',rules) or ['櫻坂46']
 for a in articles:
  for key in ['status','reason','last_seen_at']:a.pop(key,None)
 sources=read(ROOT/'config/sources.json',[]);authors=[]
 blocked=read(ROOT/'config/overrides.json',{}).get('blocked_authors',[])
 for s in sources:
  if not s.get('enabled') or s['id'] in blocked:continue
  own=[a for a in articles if a['author_id']==s['id']]
  authors.append({k:s[k] for k in ('id','name','url','platform')}|{'count':len(own),'themes':[c for c,n in collections.Counter(c for a in own for c in a['categories']).most_common(3)]})
 authors.sort(key=lambda a:a['name'])
 data={'articles':articles,'authors':authors,'settings':settings,'categories':list(rules['categories']),'groups':list(GROUP_ORDER),'pickups':curated_pickups(articles,read(ROOT/'config/pickups.json',[])),'status':read(ROOT/'state/status.json',{})}
 out=ROOT/'dist';out.mkdir(exist_ok=True)
 for p in (ROOT/'web').iterdir():shutil.copy2(p,out/p.name)
 write(out/'data/articles.json',articles);write(out/'data/authors.json',authors);write(out/'data/status.json',data['status'])
 payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
 (out/'data.js').write_text('window.ANTENNA='+payload+';\n',encoding='utf-8')
 template=(ROOT/'web/index.html').read_text()
 # Never combine newly deployed HTML with an older cached data/app bundle.
 for asset in ('data.js','app.js','style.css','analytics.js'):
  version=hashlib.sha256((out/asset).read_bytes()).hexdigest()[:12]
  template=template.replace(chr(34)+asset+chr(34),chr(34)+asset+'?v='+version+chr(34))
 def fallback(rows):return '<ul>'+''.join('<li><a href="'+html.escape(a['url'],quote=True)+'">'+html.escape(a['title'])+'</a></li>' for a in rows)+'</ul>'
 (out/'index.html').write_text(template.replace('<!-- FALLBACK -->',fallback(articles[:40])))
 # One accessible static HTML index: no new song pages or home-page clutter.
 songs_template=(ROOT/'web/songs.html').read_text(encoding='utf-8')
 songs_html=songs_template.replace('{{SONGS_CANONICAL}}',html.escape(settings.get('base_url','').rstrip('/')+'/songs.html',quote=True))
 songs_html=songs_html.replace('<!-- SONG_INDEX_CONTENT -->',song_index_content(articles,sources,rules))
 songs_html=songs_html.replace('"analytics.js"','"analytics.js?v='+hashlib.sha256((out/'analytics.js').read_bytes()).hexdigest()[:12]+'"')
 (out/'songs.html').write_text(songs_html,encoding='utf-8')
 base=settings.get('base_url','').rstrip('/')
 ad=out/'authors';shutil.rmtree(ad,ignore_errors=True);ad.mkdir()
 for a in authors:
  page=template.replace('<head>','<head><base href="../">')
  author_title=html.escape(a['name']+'の記事｜坂道考察アンテナ')
  author_desc=html.escape(a['name']+'の坂道シリーズに関する考察・批評・感想記事を探せます。元のブログやnoteへのリンクを掲載しています。',quote=True)
  author_url=base+'/authors/'+urllib.parse.quote(a['id'],safe='')+'.html' if base else ''
  page=re.sub(r'<title>[^<]*</title>','<title>'+author_title+'</title>',page,count=1)
  page=re.sub(r'<meta name="description" content="[^"]*">','<meta name="description" content="'+author_desc+'">',page,count=1)
  if author_url:
   page=re.sub(r'<link rel="canonical" href="[^"]*">','<link rel="canonical" href="'+html.escape(author_url,quote=True)+'">',page,count=1)
  else:
   page=re.sub(r'<link rel="canonical" href="[^"]*">','',page,count=1)
  page=page.replace('</head>','<script>window.PRESET_AUTHOR='+json.dumps(a['id'])+';</script></head>')
  page=page.replace('<!-- FALLBACK -->',fallback([x for x in articles if x['author_id']==a['id']]))
  (ad/(a['id']+'.html')).write_text(page)
 (out/'contact.html').write_text((ROOT/'web/contact.html').read_text().replace('{{CONTACT_URL}}',html.escape(settings.get('contact_url',''),quote=True)).replace('"analytics.js"','"analytics.js?v='+hashlib.sha256((out/'analytics.js').read_bytes()).hexdigest()[:12]+'"'))
 (out/'.nojekyll').touch()
 if base:
  pages=[base+'/',base+'/contact.html',base+'/songs.html']+[base+'/authors/'+a['id']+'.html' for a in authors]
  (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+html.escape(u)+'</loc></url>' for u in pages)+'</urlset>')
  (out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+base+'/sitemap.xml\n')
 else:(out/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
 print(f'Built {len(articles)} articles / {len(authors)} authors')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--public',action='store_true');build(p.parse_args().public)
