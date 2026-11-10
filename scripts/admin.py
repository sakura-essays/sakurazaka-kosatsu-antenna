"""Admin actions use GitHub workflow_dispatch. Input never becomes shell code."""
import os,re,urllib.parse
from collect import ROOT,read,write,fetch,parse,canonical
import xml.etree.ElementTree as ET

def main():
 action=os.environ.get('ADMIN_ACTION','update');value=os.environ.get('TARGET_URL','').strip();sid=os.environ.get('SOURCE_ID','').strip()
 sources=read(ROOT/'config/sources.json',[]);overrides=read(ROOT/'config/overrides.json',{})
 if action=='update':return
 if action=='add_candidate':
  url=canonical(value).rstrip('/');p=urllib.parse.urlsplit(url)
  if p.hostname=='note.com' and re.fullmatch('/[A-Za-z0-9_]+',p.path):platform='note';feed=url+'/rss'
  elif p.hostname and p.hostname.endswith(('.hatenablog.com','.hatenablog.jp','.hateblo.jp')) and p.path=='':platform='はてなブログ';feed=url+'/rss'
  else:raise ValueError('URL自動登録はnote・はてなブログのみ。その他RSSはconfig/sources.jsonに確認後登録してください。')
  if any(s['url'].rstrip('/')==url for s in sources):raise ValueError('Already registered/candidate')
  data,_=fetch(feed);items=list(parse(data))
  if not items:raise ValueError('Feed is empty')
  name=ET.fromstring(data).findtext('channel/title') or p.hostname
  sid=re.sub('[^A-Za-z0-9_-]','_',p.path.strip('/') if platform=='note' else p.hostname.split('.')[0])
  if any(s['id']==sid for s in sources):raise ValueError('ID collision: choose a unique ID in config/sources.json')
  sources.append(dict(id=sid,name=name,url=url,feed=feed,platform=platform,enabled=False,verification='管理者が内容・利用条件を確認するまで非公開'))
  write(ROOT/'config/sources.json',sources)
  write(ROOT/'state/candidate-'+sid+'.json',{'source_id':sid,'sample':[{'title':i['title'],'url':i['url'],'published_at':i['published_at']} for i in items[:10]]})
  print('Candidate added, NOT published:',sid)
 elif action in ('approve_source','remove_source'):
  source=next((s for s in sources if s['id']==sid),None)
  if not source:raise ValueError('Unknown source_id')
  source['enabled']=action=='approve_source'
  if action=='remove_source':overrides.setdefault('blocked_authors',[]).append(sid)
  else:overrides['blocked_authors']=[x for x in overrides.get('blocked_authors',[]) if x!=sid]
  write(ROOT/'config/sources.json',sources);write(ROOT/'config/overrides.json',overrides)
 elif action in ('approve_article','hold_article','remove_article'):
  u=canonical(value)
  if action=='remove_article':overrides.setdefault('blocked_urls',[]).append(u)
  else:
   overrides['blocked_urls']=[x for x in overrides.get('blocked_urls',[]) if x!=u]
   overrides.setdefault('articles',{}).setdefault(u,{})['status']='published' if action=='approve_article' else 'pending'
   if action=='approve_article':overrides['articles'][u]['verified_nonfiction']=True
  write(ROOT/'config/overrides.json',overrides)
 else:raise ValueError('Unsupported action')
if __name__=='__main__':main()
