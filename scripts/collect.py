"""RSS/Atom plus manually verified metadata. No article scraping, body storage, or third-party packages."""
import argparse, datetime as dt, email.utils, hashlib, html, ipaddress, json, pathlib, re, socket, sys, time, unicodedata
import urllib.request, urllib.error, urllib.parse, urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parents[1]
UTC=dt.timezone.utc
UA='SakuraEssayAntenna/1.0 (noncommercial RSS index)'
LIMIT=4_000_000

def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def plain(s):
    p=Text();p.feed(s or '');return ' '.join(p.parts).strip()

def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s)).casefold().replace('山崎天','山﨑天')

def canonical(url):
    p=urllib.parse.urlsplit(url.strip())
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password: raise ValueError('unsafe article URL')
    q=[(k,v) for k,v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','ref','hl')]
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),p.path,urllib.parse.urlencode(q),''))

def safe_url(url):
    p=urllib.parse.urlsplit(canonical(url))
    if p.scheme!='https' or p.port not in (None,443):raise ValueError('HTTPS public endpoints only')
    # Known publisher hosts also work through environments whose HTTPS proxy resolves DNS.
    if p.hostname=='note.com' or p.hostname.endswith(('.hatenablog.com','.hatenablog.jp','.hateblo.jp')):return url
    for addr in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(addr[4][0]).is_global:raise ValueError('Private address blocked')
    return url

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url,headers=None):
    safe_url(url)
    req=urllib.request.Request(url,headers={'User-Agent':UA,**(headers or {})})
    with urllib.request.build_opener(Redirect()).open(req,timeout=25) as r:
        data=r.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('Feed exceeds 4 MB limit')
        return data,dict(r.headers)

def date(value):
    try:d=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,AttributeError):
        try:d=email.utils.parsedate_to_datetime(value)
        except (ValueError,TypeError):return None
    if not d or not d.tzinfo:return None
    return d.astimezone(UTC).isoformat()

def parse(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD/entities not allowed')
    root=ET.fromstring(data)
    if root.tag.split('}')[-1] not in ('rss','feed','RDF'):raise ValueError('Not an RSS/Atom feed')
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item','entry'):continue
        values={}
        for node in item:
            key=node.tag.split('}')[-1]
            if key=='link' and node.attrib.get('href'):
                if node.attrib.get('rel','alternate')=='alternate':values['link']=node.attrib['href']
            elif node.text:values[key]=node.text
        yield dict(title=html.unescape(values.get('title','')).strip(),url=values.get('link',''),published_at=date(values.get('pubDate') or values.get('published') or values.get('date')),text=plain(values.get('encoded') or values.get('content') or values.get('description') or values.get('summary') or ''))

def song_match(song,text):
    key=norm(song)
    if key=='buddies':
        return any(token in text for token in ('「buddies」','『buddies』','"buddies"','楽曲buddies'))
    if re.fullmatch('[a-z]+',key):return bool(re.search(r'(?<![a-z])'+re.escape(key)+r'(?![a-z])',text))
    return key in text

GROUP_ORDER=('乃木坂46','櫻坂46','日向坂46')

def fiction_guard(title,text):
    """Article-level guard. Creative work elsewhere never disqualifies an author."""
    t=unicodedata.normalize('NFKC',title)
    b=unicodedata.normalize('NFKC',text or '')
    fiction=r'妄ツイ|妄リク|夢小説|創作小説|二次創作|夢日記|恋愛小説|短編小説|連載小説|妄想小説|妄想ストーリー'
    criticism=r'批評|考察|レビュー|感想|文化|について|とは'
    if re.search(fiction,t) and not re.search(criticism,t):
        return 'excluded','創作作品の明示（記事単位）'
    if re.search(r'(?:この物語は|この作品は|ここから[^。]{0,40})(?:[^。]{0,40})フィクション|配役も架空|妄想の中で開催|メンバーとは何ら関係のない物語',b):
        return 'excluded','本文に架空の物語・公演である明示'
    # A real MV/drama may contain dialogue, romance and fictional characters.
    # Ambiguous fiction signals go to review, never straight to publication.
    if (re.search(fiction,t+' '+b) or re.search(r'[〇○]{2}[「:：]',b)):
        return 'pending','創作の手掛かりあり・批評や引用との区別を確認待ち'
    if re.search(r'第\s*[0-9０-９一二三四五六七八九十]+\s*話|幼馴染|幼なじみ|同棲',t) and not re.search(criticism,t):
        return 'pending','物語形式の可能性・実活動との関係を確認待ち'
    return None

def publication_gate(source,title,text,status,reason,override):
    guard=fiction_guard(title,text)
    if guard and not override.get('verified_nonfiction'):
        return guard
    if source.get('article_policy')=='review_required' and status=='published' and not (override.get('status')=='published' and override.get('verified_nonfiction')):
        return 'pending','創作混在の書き手・記事ごとの確認待ち'
    return status,reason

def detect_groups(title,text,rules):
    """Assign group(s) from the article title first; body text is only a fallback."""
    t,b=norm(title),norm(text)
    config=rules.get('group_rules',{})
    title_matches=[]
    body_matches=[]
    for group in GROUP_ORDER:
        spec=config.get(group,{})
        keys=[norm(k) for k in spec.get('keywords',[])]
        members=[norm(m) for m in spec.get('members',[])]
        songs=spec.get('songs',[])
        if (any(k in t for k in keys) or any(m in t for m in members)
                or any(song_match(s,t) for s in songs)):
            title_matches.append(group)
        if any(k in b for k in keys):
            body_matches.append(group)
    if title_matches:return title_matches
    # Several groups in the excerpt without a title clue cannot be attributed safely.
    return body_matches if len(body_matches)==1 else []

def creator_focus(title,text=''):
    """Title-led essays about Akimoto or production staff, not incidental credits."""
    t=norm(title)
    if not t:return False
    perspective=('なぜ','どう','考察','批評','評価','論','分析','構造','功罪','課題','問題',
                 '責任','役割','必要','離れ','関与','賛否','行き詰まり','未来','理由',
                 '影響','限界','矛盾','作詞','歌詞','プロデュース','制作',
                 '振付','演出','衣装','感覚','言葉','終活','変え','思う','について',
                 'もの','仕事','関係','仕組み','レビュー','何を','予想','やめろ','書け','書く','凄さ','作れ','読む')
    if not any(word in t for word in perspective):return False
    if '秋元康' in t or '秋元さん' in t or '秋元p' in t:return True
    if any(group in t for group in ('乃木坂','櫻坂','欅坂','日向坂','akb48','坂道')) and any(
        focus in t for focus in ('表現は誰が作','誰が作っている','制作体制','制作者の役割')):
        return True
    creators=('takahiro','今野義雄','茅野しのぶ','杉山勝彦','いしわたり淳治','池田一真')
    maker_terms=('制作','作詞','作曲','歌詞','振付','衣装','演出','プロデュース',
                 '運営','映像','mv','楽曲','フォーメーション','表現','振り付け','いなかったら','読む')
    return (any(name in t for name in creators)
            and any(word in t for word in maker_terms)
            and any(group in norm(title+' '+text) for group in
                    ('乃木坂','櫻坂','欅坂','日向坂','akb48','坂道','48グループ')))

def classify(title,text,rules):
    t,b=norm(title),norm(text);whole=t+' '+b
    members=[m for m in rules['members'] if norm(m) in whole]
    songs=[s for s in rules['songs'] if song_match(s,whole)]
    for spec in rules.get('group_rules',{}).values():
        for m in spec.get('members',[]):
            if norm(m) in whole and m not in members:members.append(m)
        for s in spec.get('songs',[]):
            if song_match(s,whole) and s not in songs:songs.append(s)
    groups=detect_groups(title,text,rules)
    title_groups=detect_groups(title,'',rules)
    body_groups=detect_groups('',text,rules)
    member_title=any(norm(m) in t for m in members)
    song_title=any(song_match(s,t) for s in songs)
    analysis=any(norm(k) in whole for k in ['考察','感想','批評','レビュー','ライブ','歌詞','MV','ダンス','パフォーマンス'])
    if any(k in t for k in ['自己紹介','このnoteについて','お知らせ','販売開始','商品紹介','アフィリエイト']):
        status,reason='pending','告知・自己紹介・宣伝の可能性'
    elif title_groups:
        # A song title alone is less convincing than a group/member/TV show.
        explicit=any(norm(k) in t for spec in rules.get('group_rules',{}).values()
                     for k in spec.get('keywords',[])) or member_title
        if explicit or analysis or body_groups:
            status,reason='published','タイトルに坂道グループ・メンバー・楽曲などの手掛かり'
        else:
            status,reason='pending','楽曲名のみで主題が不明'
    elif groups and analysis:
        status,reason='published','RSS本文に坂道グループ名と考察・感想の文脈'
    elif groups or members or song_title:
        status,reason='pending','関連の手掛かりはあるが主題が不明'
    elif not text:
        status,reason='pending','RSS本文がなく判定材料不足'
    else:
        status,reason='excluded','取得できたRSSの範囲で関連性なし（全文は未確認）'
    cats=[cat for cat,keys in rules['categories'].items() if any(norm(k) in whole for k in keys)]
    if member_title and 'メンバー考察・人物論' not in cats:cats.insert(0,'メンバー考察・人物論')
    if song_title and '楽曲・歌詞考察' not in cats:cats.append('楽曲・歌詞考察')
    if creator_focus(title,text):
        if '秋元康・制作者論' not in cats:cats.append('秋元康・制作者論')
        if status!='published' and not any(k in t for k in
             ('自己紹介','このnoteについて','お知らせ','販売開始','商品紹介','アフィリエイト')):
            status,reason='published','タイトルで確認できる秋元康・制作者への考察'
    guard=fiction_guard(title,text)
    if guard:status,reason=guard
    return status,reason,cats or ['その他の感想・批評'],members,songs

def run(cache_dir=None):
    now=dt.datetime.now(UTC);stamp=now.isoformat();rules=read(ROOT/'config/rules.json',{})
    sources=read(ROOT/'config/sources.json',[]);overrides=read(ROOT/'config/overrides.json',{})
    allowed={s['id'] for s in sources if s.get('enabled') and s['id'] not in overrides.get('blocked_authors',[])}
    blocked={canonical(u) for u in overrides.get('blocked_urls',[])}
    prior=read(ROOT/'state/articles.json',[])
    records={a['url']:a for a in prior if a['author_id'] in allowed and a['url'] not in blocked}
    # Earlier releases curated Sakura/Keyaki only. Title clues override that
    # legacy default, while group-ambiguous old articles keep their grouping.
    for article in records.values():
        if not article.get('groups'):
            article['groups']=(detect_groups(article['title'],'',rules)
                               or ([] if creator_focus(article['title'])
                                   and '秋元康・制作者論' in article.get('categories',[])
                                   else ['櫻坂46']))

    state=read(ROOT/'state/feeds.json',{});statuses=[];robots={};success=0
    for source in sources:
        if source['id'] not in allowed:continue
        sid=source['id'];url=source['feed'];log={'id':sid,'checked_at':stamp};old=state.get(sid,{})
        try:
            if cache_dir:
                data=(pathlib.Path(cache_dir)/(sid+'.xml')).read_bytes();headers={}
            else:
                host=urllib.parse.urlsplit(url).netloc
                if host not in robots:
                    rp=urllib.robotparser.RobotFileParser()
                    try:rd,_=fetch('https://'+host+'/robots.txt');rp.parse(rd.decode('utf-8').splitlines())
                    except urllib.error.HTTPError as e:
                        if e.code==404:rp.parse([])
                        else:raise
                    robots[host]=rp
                if not robots[host].can_fetch(UA,url):raise ValueError('robots.txt disallows feed')
                time.sleep(1)
                cond={}
                if old.get('etag'):cond['If-None-Match']=old['etag']
                if old.get('modified'):cond['If-Modified-Since']=old['modified']
                data,headers=fetch(url,cond)
            items=list(parse(data))
            if not items:raise ValueError('Empty feed; existing articles retained')
            count=0
            for item in items:
                try:u=canonical(item['url'])
                except ValueError:continue
                if u in blocked or not item['title']:continue
                # A feed may not publish links for a different site/author.
                home=urllib.parse.urlsplit(source['url']);target=urllib.parse.urlsplit(u)
                if target.hostname!=home.hostname or (home.hostname=='note.com' and not target.path.startswith(home.path.rstrip('/')+'/n/')):continue
                status,reason,cats,members,songs=classify(item['title'],item['text'],rules)
                published=item['published_at']
                if not published or dt.datetime.fromisoformat(published)>now+dt.timedelta(minutes=10):status,reason='pending','公開日時が未確認・未来日'
                override=overrides.get('articles',{}).get(u,{})
                if published:status=override.get('status',status)
                if status not in ('published','pending','excluded'):raise ValueError('Invalid article status override')
                prev=records.get(u,{})
                # Keep an already published article visible after dictionary changes.
                # Explicit administrator status overrides always take precedence.
                if (prev.get('status')=='published' and status!='published'
                        and 'status' not in override and prev.get('title')==item['title']):
                    status,reason='published','以前の公開判定を維持'
                status,reason=publication_gate(source,item['title'],item['text'],status,reason,override)
                if not published or dt.datetime.fromisoformat(published)>now+dt.timedelta(minutes=10):
                    status,reason='pending','公開日時が未確認・未来日'
                records[u]=dict(id=hashlib.sha256(u.encode()).hexdigest()[:20],url=u,title=item['title'],author_id=sid,published_at=prev.get('published_at') or published,first_seen_at=prev.get('first_seen_at',stamp),last_seen_at=stamp,status=status,reason=reason,categories=override.get('categories',cats),members=members,songs=songs,groups=detect_groups(item['title'],item['text'],rules) or prev.get('groups',[]))
                count+=1
                warning=fiction_guard(item['title'],item['text'])
                if warning:records[u]['content_warning']=list(warning)
            state[sid]={'etag':headers.get('ETag'),'modified':headers.get('Last-Modified'),'last_success':stamp}
            log.update(status='ok',items=count,last_success=stamp);success+=1
        except urllib.error.HTTPError as e:
            if e.code==304:log.update(status='unchanged',last_success=stamp);old['last_success']=stamp;state[sid]=old;success+=1
            else:log.update(status='error',error='HTTP '+str(e.code),last_success=old.get('last_success'))
        except Exception as e:log.update(status='error',error=str(e)[:300],last_success=old.get('last_success'))
        statuses.append(log)
        print(sid,log['status'],log.get('items',''),log.get('error',''),flush=True)
    # Topic-specific note magazine feeds can recover essays missing from the
    # author's general recent-25 RSS window. Preserve the original author ID.
    for magazine in read(ROOT/'config/magazine_feeds.json',[]):
        sid=magazine['author_id']
        if sid not in allowed:continue
        source=next(s for s in sources if s['id']==sid)
        feed=canonical(magazine['feed'])
        prefix=source['url'].rstrip('/')+'/m/'
        if not feed.startswith(prefix) or not feed.endswith('/rss'):
            raise ValueError('Magazine feed must be an RSS URL below its author profile')
        feed_id='magazine:'+sid+':'+feed.split('/m/',1)[1].split('/',1)[0]
        old=state.get(feed_id,{})
        log={'id':sid,'feed_name':magazine.get('name','magazine RSS'),'checked_at':stamp}
        try:
            host=urllib.parse.urlsplit(feed).netloc
            if host not in robots:
                rp=urllib.robotparser.RobotFileParser()
                try:
                    rd,_=fetch('https://'+host+'/robots.txt')
                    rp.parse(rd.decode('utf-8').splitlines())
                except urllib.error.HTTPError as e:
                    if e.code==404:rp.parse([])
                    else:raise
                robots[host]=rp
            if not robots[host].can_fetch(UA,feed):
                raise ValueError('robots.txt disallows magazine RSS')
            time.sleep(1)
            cond={}
            if old.get('etag'):cond['If-None-Match']=old['etag']
            if old.get('modified'):cond['If-Modified-Since']=old['modified']
            data,headers=fetch(feed,cond)
            items=list(parse(data))
            if not items:raise ValueError('Empty magazine RSS; previous records retained')
            count=0
            home=urllib.parse.urlsplit(source['url'])
            for item in items:
                try:u=canonical(item['url'])
                except ValueError:continue
                target=urllib.parse.urlsplit(u)
                # A magazine can contain third-party articles; index only this author.
                if u in blocked or not item['title'] or target.hostname!=home.hostname or not target.path.startswith(home.path.rstrip('/')+'/n/'):
                    continue
                status,reason,cats,members,songs=classify(item['title'],item['text'],rules)
                if magazine.get('require_creator_focus') and not creator_focus(item['title'],item['text']):
                    continue
                # General idol magazines also carry Nogizaka/Hinata-only essays.
                # Keep only confidently Sakura-relevant records when requested.
                if magazine.get('require_relevance') and status!='published':
                    continue
                pub=item['published_at']
                if not pub or dt.datetime.fromisoformat(pub)>now+dt.timedelta(minutes=10):
                    status,reason='pending','マガジンRSSの公開日時が未確認・未来日'
                # Magazine membership alone is not evidence of relevance/nonfiction.
                override=overrides.get('articles',{}).get(u,{})
                if pub:status=override.get('status',status)
                prev=records.get(u,{})
                if (prev.get('status')=='published' and status!='published'
                        and 'status' not in override and prev.get('title')==item['title']):
                    status,reason='published','以前の公開判定を維持'
                status,reason=publication_gate(source,item['title'],item['text'],status,reason,override)
                if not pub or dt.datetime.fromisoformat(pub)>now+dt.timedelta(minutes=10):
                    status,reason='pending','マガジンRSSの公開日時が未確認・未来日'
                records[u]=dict(id=hashlib.sha256(u.encode()).hexdigest()[:20],
                                url=u,title=item['title'],author_id=sid,
                                published_at=prev.get('published_at') or pub,
                                first_seen_at=prev.get('first_seen_at',stamp),
                                last_seen_at=stamp,status=status,reason=reason,
                                categories=override.get('categories',cats),
                                members=members,songs=songs,
                                groups=detect_groups(item['title'],item['text'],rules) or prev.get('groups',[]) or (['櫻坂46'] if '櫻坂' in magazine.get('name','') else []))
                count+=1
                warning=fiction_guard(item['title'],item['text'])
                if warning:records[u]['content_warning']=list(warning)
            state[feed_id]={'etag':headers.get('ETag'),
                            'modified':headers.get('Last-Modified'),
                            'last_success':stamp}
            log.update(status='ok',items=count,last_success=stamp)
            success+=1
        except urllib.error.HTTPError as e:
            if e.code==304:
                log.update(status='unchanged',last_success=stamp)
                old['last_success']=stamp;state[feed_id]=old;success+=1
            else:
                log.update(status='error',error='HTTP '+str(e.code),
                           last_success=old.get('last_success'))
        except Exception as e:
            log.update(status='error',error=str(e)[:300],
                       last_success=old.get('last_success'))
        statuses.append(log)
        print(feed_id,log['status'],log.get('items',''),log.get('error',''),flush=True)
    # Backfill curator-verified article metadata outside the limited RSS window.
    # RSS entries take precedence. Manual records persist without pretending
    # that their day-precision publication date is an exact timestamp.
    manually_added=0
    source_by_id={s['id']:s for s in sources}
    for item in read(ROOT/'config/manual_articles.json',[]):
        sid=item['author_id']
        if sid not in allowed:continue
        src=source_by_id[sid]
        u=canonical(item['url'])
        home=urllib.parse.urlsplit(src['url']);target=urllib.parse.urlsplit(u)
        if target.hostname!=home.hostname or (home.hostname=='note.com' and not target.path.startswith(home.path.rstrip('/')+'/n/')):
            raise ValueError('Manual article URL is outside its author feed')
        if u in blocked or u in records:continue
        raw_pub=item['published_at']
        parsed_pub=date(raw_pub) if 'T' in raw_pub else None
        if 'T' in raw_pub and not parsed_pub:raise ValueError('Invalid manual article timestamp')
        pub=dt.datetime.fromisoformat(parsed_pub).date() if parsed_pub else dt.date.fromisoformat(raw_pub)
        if pub>now.date():raise ValueError('Manual article date is in the future')
        cats=item.get('categories',[])
        if not cats or any(c not in rules['categories'] for c in cats):
            raise ValueError('Unknown manual article category')
        title=item['title'].strip()
        if not title:raise ValueError('Empty manual article title')
        _,_,_,members,songs=classify(title,'',rules)
        manual_override=overrides.get('articles',{}).get(u,{})
        status,reason=publication_gate(src,title,'','published','管理者が元記事のタイトル・URL・公開日を照合して追加',manual_override)
        records[u]=dict(id=hashlib.sha256(u.encode()).hexdigest()[:20],
                        url=u,title=title,author_id=sid,
                        published_at=parsed_pub or pub.isoformat(),first_seen_at=stamp,
                        last_seen_at=stamp,status=status,reason=reason,
                        categories=cats,members=members,songs=songs,
                        groups=(item['groups'] if 'groups' in item else (detect_groups(title,'',rules) or ['櫻坂46'])))
        manually_added+=1
    if manually_added:print('Manually backfilled:',manually_added,flush=True)
    # Group-neutral creator essays belong to the overall feed, not Sakura by default.
    for a in records.values():
        if (not a.get('groups') and a['status']=='published'
                and '秋元康・制作者論' not in a.get('categories',[])):
            a['status']='pending';a['reason']='対象グループを確認待ち'
    # Apply moderation also to articles no longer present in recent feeds.
    for u,a in records.items():
        o=overrides.get('articles',{}).get(u,{})
        if o.get('status') in ('published','pending','excluded') and a.get('published_at'):a['status']=o['status']
        if 'categories' in o:a['categories']=o['categories']
        elif creator_focus(a['title']) and '秋元康・制作者論' not in a.get('categories',[]):
            a.setdefault('categories',[]).append('秋元康・制作者論')
        # Apply to retained records too, including ones outside the recent RSS.
        a['status'],a['reason']=publication_gate(source_by_id[a['author_id']],a['title'],'',a['status'],a['reason'],o)
        if a.get('content_warning') and not o.get('verified_nonfiction'):
            a['status'],a['reason']=a['content_warning']
        if 'groups' in o:a['groups']=o['groups']
        stored_date=a.get('published_at') or ''
        parsed_date=date(stored_date if 'T' in stored_date else stored_date+'T00:00:00+00:00')
        if a['status']=='published' and (not parsed_date or dt.datetime.fromisoformat(parsed_date)>now+dt.timedelta(minutes=10) or (not a.get('groups') and '秋元康・制作者論' not in a.get('categories',[]))):
            a['status']='pending';a['reason']='公開日時・対象グループを確認待ち'
    articles=sorted(records.values(),key=lambda a:(a.get('published_at') or '',a['url']),reverse=True)
    write(ROOT/'state/articles.json',articles);write(ROOT/'state/feeds.json',state)
    write(ROOT/'state/review.json',[a for a in articles if a['status']!='published'])
    report={'attempted_at':stamp,'successful_feeds':success,'total_feeds':len(statuses),'feeds':statuses,'counts':{s:sum(a['status']==s for a in articles) for s in ('published','pending','excluded')}}
    write(ROOT/'state/status.json',report)
    return 0 if success and success==len(statuses) else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache-dir',help='Development only: pre-fetched RSS files');a=p.parse_args();sys.exit(run(a.cache_dir))
