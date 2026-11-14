'use strict';
// One collection boundary for every page. No tag is loaded on mirrors or opted-out browsers.
(() => {
 const ID='G-48Y73ZJHVL',KEY='antenna.analytics.disabled',VERSION='20261114';
 const page=new URL(location.href),choice=page.searchParams.get('analytics');
 try {if(choice==='off')localStorage.setItem(KEY,'1');if(choice==='on')localStorage.removeItem(KEY);}catch{}
 let optedOut=choice==='off';try{optedOut=optedOut||localStorage.getItem(KEY)==='1';}catch{}
 const test=choice==='test';
 const production=page.hostname==='sakura-essays.github.io'&&page.pathname.startsWith('/sakurazaka-kosatsu-antenna/');
 const enabled=production&&!optedOut&&!test&&!navigator.webdriver;
 window['ga-disable-'+ID]=!enabled;
 const cleanTerm=value=>{
  const text=String(value||'').normalize('NFKC').trim().replace(/\s+/g,' ');
  return /@|https?:|www\.|(?:\d[\s()+-]*){7,}/i.test(text)?'[redacted]':text.slice(0,100);
 };
 function cleanLocation(){const u=new URL(location.href);u.search='';u.hash='';for(const key of ['utm_source','utm_medium','utm_campaign','utm_content','utm_term']){const value=page.searchParams.get(key);if(value)u.searchParams.set(key,cleanTerm(value));}return u.href;}
 function referrer(){try{const u=new URL(document.referrer);return u.origin+u.pathname;}catch{return '';}}
 let state={view:page.pathname.endsWith('/songs.html')?'song_index':page.pathname.endsWith('/contact.html')?'contact':'articles'},results=0,writerQuery='',searchTimer=null,lastSearch='',searchNumber=0,view='',filterSignature='';
 const records=[],seen=new Set(),timers=new Map();let observer=null;
 function context(){return {site_view:state.view||'articles',filter_group:state.group||'all',sort_order:state.sort||'new',search_active:String(Boolean(String((state.view==='authors'?writerQuery:state.q)||'').trim())),search_scope:state.view==='authors'?'authors':'articles',search_term:cleanTerm(state.view==='authors'?writerQuery:state.q),result_count:results,measurement_version:VERSION};}
 function track(name,params={}){
  if(!enabled&&!test)return;
  const payload={...context(),...params,page_location:cleanLocation(),transport_type:'beacon'};
  if(test){records.push({event:name,...payload});showDebug();return;}
  window.gtag('event',name,payload);
 }
 function showDebug(){
  if(!document.body)return;
  let panel=document.getElementById('analytics-debug');
  if(!panel){panel=document.createElement('details');panel.id='analytics-debug';panel.open=true;panel.innerHTML='<summary>計測テスト（Googleには送信しません）</summary><pre></pre>';document.body.appendChild(panel);}
  panel.querySelector('pre').textContent=JSON.stringify(records.slice(-25),null,2);
 }
 function flushSearch(){
  clearTimeout(searchTimer);const c=context();
  if(c.search_active!=='true'){lastSearch='';return;}
  const signature=JSON.stringify([c.search_scope,c.search_term,c.filter_group,state.cat,state.member,state.song,state.author,results]);
  if(signature===lastSearch)return;
  lastSearch=signature;searchNumber++;
  track(c.search_scope==='authors'?'writer_search':'view_search_results',{zero_results:String(results===0),search_number:searchNumber});
 }
 function update(next,count,writer=''){
  const prior=context();state={...next};results=count;writerQuery=writer;
  if(view!==state.view){view=state.view;track('site_view');}
  const signature=JSON.stringify([state.group,state.cat,state.author,state.member,state.song,state.platform,state.from,state.to,state.sort]);
  if(filterSignature&&signature!==filterSignature)track('filter_change');
  filterSignature=signature;
  if(prior.search_term!==context().search_term||prior.filter_group!==context().filter_group||prior.search_scope!==context().search_scope||prior.result_count!==results){clearTimeout(searchTimer);searchTimer=setTimeout(flushSearch,750);}
  observe();
 }
 function placement(link){if(link.dataset.placement)return link.dataset.placement;if(link.closest('#pickup-list'))return 'pickup';if(link.closest('#random-essay'))return 'random';if(link.closest('.related'))return 'related';if(link.closest('.song-links'))return 'song_index';return window.PRESET_AUTHOR?'author_page':'list';}
 function articleParams(link){
  const data=window.ANTENNA||{},a=(data.articles||[]).find(a=>a.url===link.href),w=(data.authors||[]).find(w=>w.id===(a?.author_id||link.dataset.authorId));
  return {link_url:link.href,article_id:a?.id||link.dataset.articleId||'',article_title:(a?.title||link.dataset.articleTitle||link.textContent||'').trim().slice(0,100),author_id:a?.author_id||link.dataset.authorId||'',author_name:(w?.name||link.dataset.authorName||'').slice(0,100),article_group:(a?.groups||[]).join(' / ')||link.dataset.articleGroup||'unassigned',placement:placement(link)};
 }
 function observe(){
  if(!observer)return;observer.disconnect();for(const timer of timers.values())clearTimeout(timer);timers.clear();
  document.querySelectorAll('a.tracked-article').forEach(link=>observer.observe(link));
 }
 function init(){
  // The app can queue events while the asynchronous Google library loads.
  track('page_view',{page_title:document.title,page_referrer:referrer()});
  if(typeof IntersectionObserver==='function')observer=new IntersectionObserver(entries=>{
   for(const entry of entries){const link=entry.target,key=JSON.stringify([view,filterSignature,context().search_term,placement(link),link.href]);
    if(!entry.isIntersecting||entry.intersectionRatio<0.5){clearTimeout(timers.get(link));timers.delete(link);continue;}
    if(seen.has(key)||timers.has(link))continue;
    timers.set(link,setTimeout(()=>{timers.delete(link);if(!link.isConnected||document.visibilityState==='hidden')return;seen.add(key);track('article_impression',articleParams(link));},1000));
   }
  },{threshold:[0,0.5]});
  const click=e=>{if(e.type==='auxclick'&&e.button!==1||e.type==='click'&&e.button>0)return;const link=e.target.closest('a.tracked-article');if(!link)return;flushSearch();track('article_click',{...articleParams(link),search_number:searchNumber,open_method:e.type==='auxclick'?'middle':e.ctrlKey||e.metaKey?'modified':'normal'});};
  document.addEventListener('click',click);document.addEventListener('auxclick',click);
  document.addEventListener('toggle',e=>{if(e.target.matches?.('.pickup-disclosure')&&e.target.open){track('pickup_open');observe();}else if(e.target.matches?.('.related')&&e.target.open){track('related_open');observe();}},true);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'){flushSearch();for(const timer of timers.values())clearTimeout(timer);timers.clear();}else observe();});
  observe();showDebug();
 }
 // Bootstrap before app.js, but defer DOM listeners until all templates are parsed.
if(enabled){window.dataLayer=window.dataLayer||[];window.gtag=function(){window.dataLayer.push(arguments);};window.gtag('js',new Date());window.gtag('config',ID,{send_page_view:false,page_location:cleanLocation(),page_referrer:referrer(),allow_google_signals:false,allow_ad_personalization_signals:false});const script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id='+ID;document.head.appendChild(script);}
 window.AntennaAnalytics={track,update,flushSearch,observe,events:records,enabled,mode:test?'test':enabled?'on':'off'};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
