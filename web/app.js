'use strict';
(() => {
 const D=window.ANTENNA;if(!D){document.getElementById('notice').textContent='記事データを読み込めませんでした。再読み込みしてください。';return;}
 const $=id=>document.getElementById(id);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const normalize=s=>String(s).normalize('NFKC').toLowerCase().replace(/\s/g,'').replaceAll('山崎天','山﨑天');
 const url=s=>{try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?esc(u.href):'#';}catch{return '#';}};
 const byId=Object.fromEntries(D.authors.map(a=>[a.id,a]));
 const authorPath=id=>new URL('authors/'+encodeURIComponent(id)+'.html',document.baseURI).href;
 const date=s=>s?new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(s)).replaceAll('/','.'):'公開日未確認';
 const day=s=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(s));
 let state={},limit=30;
 let randomRanks=new Map();
 // Keep one stable randomized author order per page load, until explicitly remixed.
 let shuffledAuthors=[];
 let writerQuery='';
 function reshuffleAuthors(){
  shuffledAuthors=[...D.authors];
  for(let i=shuffledAuthors.length-1;i>0;i--){
   const j=Math.floor(Math.random()*(i+1));
   [shuffledAuthors[i],shuffledAuthors[j]]=[shuffledAuthors[j],shuffledAuthors[i]];
  }
 }
 reshuffleAuthors();
 function reshuffle(){const items=[...D.articles];for(let i=items.length-1;i>0;i--){const k=Math.floor(Math.random()*(i+1));[items[i],items[k]]=[items[k],items[i]];}randomRanks=new Map(items.map((a,i)=>[a.url,i]));}
 reshuffle();
 const controls=['author','member','song','platform','from','to','sort'];
 const articleGroups=a=>a.groups?.length?a.groups:(a.categories?.includes('制作者・クリエイター論')?[]:['櫻坂46']);
 const articleLabels=a=>articleGroups(a).length?articleGroups(a):['制作論'];
 const inGroup=a=>!state.group||articleGroups(a).includes(state.group);
 const allGroups=D.groups||['乃木坂46','櫻坂46','日向坂46','青葉坂46'];
 const articlesByUrl=new Map(D.articles.map(a=>[a.url,a]));
 const tones={'乃木坂46':'nogi','櫻坂46':'sakura','日向坂46':'hinata','青葉坂46':'aoba'};
 // Writer badges describe collected essay topics, not a writer's exclusive affiliation.
 const writerGroupSets=new Map(D.authors.map(a=>[a.id,new Set()]));
 for(const article of D.articles){
   const groups=writerGroupSets.get(article.author_id);
   if(groups) for(const group of articleGroups(article)) if(allGroups.includes(group)) groups.add(group);
 }
 const writerGroups=id=>allGroups.filter(group=>writerGroupSets.get(id)?.has(group));
 const toneFor=a=>articleGroups(a).length===1?(tones[articleGroups(a)[0]]||'neutral'):'neutral';
 // Relations use published metadata only. Require a concrete title-level match;
 // group/category overlap alone can never create a recommendation.
 const canonical=s=>{try{const u=new URL(s);return u.hostname==='note.com'&&/\/n\/(n[a-z0-9]+)/.test(u.pathname)?'note:'+u.pathname.match(/\/n\/(n[a-z0-9]+)/)[1]:u.origin+u.pathname.replace(/\/$/,'');}catch{return s;}};
 const genericQuotes=new Set(['乃木坂46','櫻坂46','日向坂46','欅坂46','考察','ライブ','アイドル','感想','歌詞','楽曲','選抜','アンダー','乃木坂工事中','そこ曲がったら、櫻坂？','日向坂で会いましょう','グループ運営','メンバー考察','楽曲・歌詞考察',...D.categories].map(normalize));
 const songNames=[...new Set(D.articles.flatMap(a=>a.songs||[]))];
 const memberNames=[...new Set(D.articles.flatMap(a=>a.members||[]))];
 const topicNames=['選抜制度','選抜発表','選抜とアンダー','ミーグリ','オンライン握手会','握手会','生歌','口パク','衣装デザイン','茅野しのぶ','秋元康の歌詞','卒業センター','センター交代','世代交代','合同オーディション','恋愛禁止','ファンのコール','コール問題','フォーメーション'];
 const relationFeatures=new Map(D.articles.map(a=>{
  const title=normalize(a.title);
  const quotes=[...a.title.matchAll(/[「『“\"]([^「」『』“”\"]+)[」』”\"]/g)].map(m=>m[1].trim());
  const quoted=new Set(quotes.map(normalize));
  return [a.url,{
   songs:songNames.filter(s=>{const n=normalize(s);return n.length>=3?title.includes(n):quoted.has(n);}),
   members:memberNames.filter(m=>title.includes(normalize(m))),
   phrases:quotes.filter(q=>normalize(q).length>=5&&!genericQuotes.has(normalize(q))),
   topics:topicNames.filter(t=>title.includes(normalize(t)))
  }];
 }));
 const relationCache=new Map();
 function relatedArticles(a){
  if(relationCache.has(a.url))return relationCache.get(a.url);
  const source=relationFeatures.get(a.url),seen=new Set([canonical(a.url)]),candidates=[];
  for(const b of D.articles){
   if(seen.has(canonical(b.url))||!byId[b.author_id])continue;
   const target=relationFeatures.get(b.url);
   const common=key=>source[key].filter(v=>target[key].some(t=>normalize(t)===normalize(v)));
   const songs=common('songs'),members=common('members'),phrases=common('phrases'),topics=common('topics');
   const group=articleGroups(a).some(g=>articleGroups(b).includes(g));
   const category=a.categories.some(c=>b.categories.includes(c));
   let weight=0,reason='';
   if(songs.length){weight=100;reason='共通の楽曲：'+songs[0];}
   else if(members.length){weight=70;reason='共通のメンバー：'+members[0];}
   else if(phrases.length){weight=80;reason='タイトルの共通語：'+phrases[0];}
   else if(topics.length&&group&&category){weight=40;reason='共通のテーマ：'+topics[0];}
   if(!weight)continue;
   candidates.push({article:b,reason,weight:weight+(group?3:0)+(category?2:0),other:b.author_id!==a.author_id});
  }
  // Prefer other voices within a comparable level of direct relevance.
  candidates.sort((x,y)=>Math.floor(y.weight/30)-Math.floor(x.weight/30)||Number(y.other)-Number(x.other)||y.weight-x.weight||y.article.published_at.localeCompare(x.article.published_at)||x.article.url.localeCompare(y.article.url));
  const selected=[],writers=new Set();
  for(const distinct of [true,false])for(const row of candidates){
   const b=row.article,key=canonical(b.url);
   if(selected.length===3)break;
   if(seen.has(key)||(distinct&&writers.has(b.author_id)))continue;
   selected.push(row);seen.add(key);writers.add(b.author_id);
  }
  relationCache.set(a.url,selected);return selected;
 }
 function relatedMarkup(a){
  const rows=relatedArticles(a);if(!rows.length)return '';
  return `<details class="related"><summary>関連記事を見る <span class="related-count">${rows.length}件</span><span class="sr-only">：${esc(a.title)}</span></summary><div class="related-body"><p class="related-note">公開メタデータの共通点から。異なる書き手の視点も探せます。</p><ul>${rows.map(({article:b,reason})=>`<li><p class="related-reason">${esc(reason)}</p><a class="tracked-article related-title" data-author-id="${esc(b.author_id)}" data-article-title="${esc(b.title)}" href="${url(b.url)}" target="_blank" rel="noopener">${esc(b.title)}<span class="sr-only">（元記事を新しいタブで開く）</span></a><div class="related-meta"><a href="${esc(authorPath(b.author_id))}">${esc(byId[b.author_id].name)}</a><time datetime="${esc(b.published_at)}">${date(b.published_at)}</time></div></li>`).join('')}</ul></div></details>`;
 }
 const picks=(D.pickups||[]).map(p=>({article:articlesByUrl.get(p.url),note:p.note})).filter(p=>p.article&&byId[p.article.author_id]);
 for(let i=picks.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[picks[i],picks[j]]=[picks[j],picks[i]];}
 // An opt-in, non-editorial way to encounter an archived essay. Choose a writer
 // first so prolific authors are not automatically overrepresented.
 const curatedUrls=new Set(picks.map(p=>p.article.url));
 const sampledUrls=new Set();
 let lastSampledAuthor='',randomEssay=null;
 function randomPool(){
  const cutoff=Date.now()-30*24*60*60*1000;
  return D.articles.filter(a=>a.published_at&&Date.parse(a.published_at)<=cutoff
   &&byId[a.author_id]&&!curatedUrls.has(a.url)
   &&inGroup(a)&&(!state.cat||a.categories.includes(state.cat)));
 }
 function randomAllowed(){
  return !(state.q||state.author||state.member||state.song||state.platform||state.from||state.to);
 }
 function renderRandomEssay(){
  const enabled=randomAllowed()&&randomPool().length>0;
  const button=$('random-essay-trigger'),panel=$('random-essay');
  button.hidden=!enabled;
  if(!enabled||!randomEssay||!randomPool().some(a=>a.url===randomEssay.url)){
   if(!enabled||randomEssay&&!randomPool().some(a=>a.url===randomEssay.url))randomEssay=null;
   panel.hidden=true;
   button.setAttribute('aria-expanded','false');
   return;
  }
  const a=randomEssay,w=byId[a.author_id];
  panel.hidden=false;
  button.setAttribute('aria-expanded','true');
  $('random-essay-body').innerHTML=`<div class="random-essay-meta"><time datetime="${esc(a.published_at)}">${date(a.published_at)}</time><span>${esc(articleLabels(a).join(' / '))}</span><span>${esc(w.platform)}</span></div><h3><a class="tracked-article" data-author-id="${esc(a.author_id)}" data-article-title="${esc(a.title)}" href="${url(a.url)}" target="_blank" rel="noopener">${esc(a.title)} <span aria-hidden="true">↗</span><span class="sr-only">（元記事を新しいタブで開く）</span></a></h3><a class="random-essay-author" href="${esc(authorPath(w.id))}">${esc(w.name)}</a>`;
 }
 function drawRandomEssay(){
  let available=randomPool();
  if(!available.length){randomEssay=null;renderRandomEssay();return;}
  let fresh=available.filter(a=>!sampledUrls.has(a.url));
  if(!fresh.length){sampledUrls.clear();fresh=available;}
  const otherAuthors=fresh.filter(a=>a.author_id!==lastSampledAuthor);
  if(otherAuthors.length)fresh=otherAuthors;
  const writers=[...new Set(fresh.map(a=>a.author_id))];
  const writer=writers[Math.floor(Math.random()*writers.length)];
  const writerArticles=fresh.filter(a=>a.author_id===writer);
  randomEssay=writerArticles[Math.floor(Math.random()*writerArticles.length)];
  sampledUrls.add(randomEssay.url);
  lastSampledAuthor=writer;
  renderRandomEssay();
 }
 function renderPickups(){
  const block=$('pickup-section');
  const narrowed=state.q||state.cat||state.author||state.member||state.song||state.platform||state.from||state.to;
  const visible=narrowed?[]:picks.filter(p=>inGroup(p.article));
  block.hidden=!visible.length;
  if(!visible.length){$('pickup-list').innerHTML='';return;}
  $('pickup-list').innerHTML=visible.map(({article:a,note})=>{
   const w=byId[a.author_id],groups=articleGroups(a);
   const tone=toneFor(a);
   const themes={
    'メンバー考察・人物論':['person','人物を読む'],
    '楽曲・歌詞考察':['music','楽曲・歌詞を読む'],
    'ダンス・パフォーマンス考察':['performance','表現を読む'],
    'ライブ・コンサート':['live','ライブの余韻'],
    'そこ曲がったら、櫻坂？':['program','番組を読む'],
    '乃木坂工事中':['program','番組を読む'],
    '日向坂で会いましょう':['program','番組を読む'],
    'グループ運営・アイドル論':['group','グループを読む'],
    'ファンダム・ファン文化':['group','ファン文化を読む']
   };
   const [theme,label]=themes[a.categories.find(c=>themes[c])]||['essay','考察・感想'];
   const titleId='pickup-title-'+a.id;
   return `<article class="pickup-card pickup-tone-${tone} pickup-theme-${theme}"><a class="pickup-link tracked-article" aria-labelledby="${esc(titleId)}" data-author-id="${esc(a.author_id)}" data-article-title="${esc(a.title)}" href="${url(a.url)}" target="_blank" rel="noopener"><div class="pickup-cover" aria-hidden="true"><span class="pickup-cover-group">${esc(groups.join(' / '))}</span><p class="pickup-cover-title">${esc(a.title)}</p><span class="pickup-cover-theme">${esc(label)}</span></div><div class="pickup-body"><span class="sr-only">${esc(groups.join('、'))}。${esc(label)}。</span><h3 id="${esc(titleId)}">${esc(a.title)}<span class="sr-only">（元記事を新しいタブで開く）</span></h3><p class="pickup-author">${esc(w.name)}</p><p class="pickup-reason">${esc(note)}</p></div></a></article>`;
  }).join('');
 }
 function options(id,items){$(id).insertAdjacentHTML('beforeend',items.map(([v,l])=>`<option value="${esc(v)}">${esc(l)}</option>`).join(''));}
 options('author',D.authors.map(a=>[a.id,a.name]));
 for(const [id,field] of [['member','members'],['song','songs']])options(id,[...new Set(D.articles.flatMap(a=>a[field]))].sort((a,b)=>a.localeCompare(b,'ja')).map(x=>[x,x]));
 function readState(){const p=new URLSearchParams(location.search);state={view:p.get('view')||'articles',group:allGroups.includes(p.get('group'))?p.get('group'):'',q:p.get('q')||'',cat:p.get('cat')||'',author:p.has('author')?p.get('author'):(window.PRESET_AUTHOR||''),member:p.get('member')||'',song:p.get('song')||'',platform:p.get('platform')||'',from:p.get('from')||'',to:p.get('to')||'',sort:p.get('sort')||'new'};if(!['articles','authors','about'].includes(state.view))state.view='articles';limit=30;sync();render();}
 function sync(){ $('query').value=state.q;controls.forEach(id=>$(id).value=state[id]);if(controls.some(k=>k!=='sort'&&state[k]))document.querySelector('.filters').open=true;}
 function save(){const p=new URLSearchParams();Object.entries(state).forEach(([k,v])=>{if(v)p.set(k,v)});if(window.PRESET_AUTHOR&&!state.author)p.set('author','');history.pushState(null,'','?'+p.toString());render();}
 function reset(){state={view:'articles',group:'',q:'',cat:'',author:'',member:'',song:'',platform:'',from:'',to:'',sort:'new'};limit=30;sync();save();}
 function card(a){const w=byId[a.author_id];return `<article class="article"><div class="article-top"><time datetime="${esc(a.published_at)}">${date(a.published_at)}</time><span class="group-labels">${articleLabels(a).map(g=>`<span class="group-label tone-${toneFor(a)}">${esc(g)}</span>`).join('')}</span><span class="platform">${esc(w.platform)}</span></div><h3><a class="tracked-article" data-author-id="${esc(a.author_id)}" data-article-title="${esc(a.title)}" href="${url(a.url)}" target="_blank" rel="noopener">${esc(a.title)}<span class="external" aria-hidden="true">↗</span><span class="sr-only">（元記事を新しいタブで開く）</span></a></h3><div class="article-bottom"><a class="author-link" href="${esc(authorPath(w.id))}">${esc(w.name)}</a><div class="tags">${a.categories.map(c=>`<button class="tag" aria-pressed="${state.cat===c}" data-category="${esc(c)}">${esc(c)}</button>`).join('')}</div></div>${relatedMarkup(a)}</article>`;}
 function renderActiveFilters(){
  const labels={group:'グループ',q:'検索',cat:'テーマ',author:'書き手',member:'メンバー',song:'楽曲',platform:'媒体',from:'開始日',to:'終了日'};
  const active=Object.entries(labels).filter(([key])=>state[key]);
  $('active-filters').hidden=!active.length;
  $('active-filters').innerHTML=active.map(([key,label])=>{
   const value=key==='author'?(byId[state.author]?.name||state.author):state[key];
   return `<button type="button" class="filter-chip" data-clear-filter="${key}" aria-label="${esc(label+'：'+value+' の条件を解除')}">${esc(label)}：${esc(value)} <span aria-hidden="true">×</span></button>`;
  }).join('');
 }
 function renderAuthors(){
  const words=writerQuery.trim().split(/\s+/).filter(Boolean).map(normalize);
  const matching=shuffledAuthors.filter(a=>
    (!state.group||D.articles.some(x=>x.author_id===a.id&&inGroup(x)))&&
    words.every(w=>normalize(a.name+' '+a.id).includes(w))
  );
  $('author-result-count').textContent=`${matching.length}人の書き手`;
  $('author-clear').hidden=!writerQuery;
  $('authors-grid').innerHTML=matching.length?matching.map(a=>`<article class="writer-card"><span class="platform">${esc(a.platform)}</span><h3><a href="${esc(authorPath(a.id))}">${esc(a.name)}</a></h3><div class="writer-groups" aria-label="収集記事で扱うグループ">${writerGroups(a.id).map(g=>`<span class="group-label tone-${tones[g]||'neutral'}">${esc(g)}</span>`).join('')||'<span class="writer-group-none">グループ別の収集記事なし</span>'}</div><p class="count">収集済み ${a.count} 記事</p><p class="themes">${esc(a.themes.join(' / '))}</p><div class="writer-bottom"><a href="${esc(authorPath(a.id))}">記事一覧へ →</a><a href="${url(a.url)}" target="_blank" rel="noopener">元サイト ↗</a></div></article>`).join(''):'<p class="author-empty">該当する書き手が見つかりません。別の名前やユーザーIDで検索してください。</p>';
 }
 function balanced(items){const buckets=new Map();for(const a of items){if(!buckets.has(a.author_id))buckets.set(a.author_id,[]);buckets.get(a.author_id).push(a);}const out=[];let more=true;while(more){more=false;for(const bucket of buckets.values()){if(bucket.length){out.push(bucket.shift());more=true}}}return out;}
 function render(){
  document.querySelectorAll('[data-view]').forEach(a=>{a.classList.toggle('active',a.dataset.view===state.view);if(a.dataset.view===state.view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('article-view').hidden=state.view!=='articles';$('authors-view').hidden=state.view!=='authors';$('about-view').hidden=state.view!=='about';
  if(state.view==='authors'){renderAuthors();return;}
  if(state.view!=='articles')return;
  renderRandomEssay();
  $('group-tabs').innerHTML=[['','すべて'],...allGroups.map(g=>[g,g])].map(([g,label])=>`<button type="button" class="group-tab ${state.group===g?'active':''}" data-group="${esc(g)}" data-tone="${tones[g]||'neutral'}" aria-pressed="${state.group===g}">${esc(label)}<span class="num">${D.articles.filter(a=>!g||articleGroups(a).includes(g)).length}</span></button>`).join('');
  renderPickups();
  $('categories').innerHTML=['',...D.categories].map(c=>`<button class="category ${state.cat===c?'active':''}" aria-pressed="${state.cat===c}" data-category="${esc(c)}"><span>${esc(c||'すべての記事')}</span><span class="num">${D.articles.filter(a=>inGroup(a)&&(!c||a.categories.includes(c))).length}</span></button>`).join('');
  let filtered=D.articles.filter(a=>{
   const author=byId[a.author_id];const hay=normalize([a.title,author.name,...a.members,...a.songs,...a.categories].join(' '));
   return inGroup(a)&&state.q.trim().split(/\s+/).every(q=>hay.includes(normalize(q)))&&(!state.cat||a.categories.includes(state.cat))&&(!state.author||a.author_id===state.author)&&(!state.member||a.members.includes(state.member))&&(!state.song||a.songs.includes(state.song))&&(!state.platform||author.platform===state.platform)&&(!state.from||day(a.published_at)>=state.from)&&(!state.to||day(a.published_at)<=state.to);
  });
  if(state.sort==='random')filtered.sort((a,b)=>randomRanks.get(a.url)-randomRanks.get(b.url));
  else {
   filtered.sort((a,b)=>state.sort==='old'?a.published_at.localeCompare(b.published_at)||a.url.localeCompare(b.url):b.published_at.localeCompare(a.published_at)||a.url.localeCompare(b.url));
   if(state.sort==='balanced')filtered=balanced(filtered);
  }
  $('reshuffle').hidden=state.sort!=='random';
  const author=byId[state.author];$('author-profile').hidden=!author;
  if(author)$('author-profile').innerHTML=`<p class="eyebrow">WRITER</p><h2>${esc(author.name)}</h2><p>${esc(author.platform)} · 収集済み ${author.count} 記事</p><p>主なテーマ（自動集計）：${esc(author.themes.join(' / '))}</p><a href="${url(author.url)}" target="_blank" rel="noopener">書き手のサイトへ ↗</a>`;
  const has=state.group||state.q||state.cat||state.author||state.member||state.song||state.platform||state.from||state.to;
  $('list-title').textContent=has?'条件に合う記事':state.sort==='old'?'過去の記事':state.sort==='balanced'?'書き手を交互に':state.sort==='random'?'ランダムに読む':'新着記事';
  $('list-eyebrow').textContent=has?'EXPLORE ESSAYS':state.sort==='old'?'FROM THE ARCHIVE':state.sort==='random'?'DISCOVER AT RANDOM':'LATEST ESSAYS';
  renderActiveFilters();
  $('result-count').textContent=`${filtered.length} 件${filtered.length>limit?` / ${limit} 件を表示`:''}`;
  $('articles').innerHTML=filtered.length?filtered.slice(0,limit).map(card).join(''):'<div class="empty"><p>この条件に合う記事はまだありません。</p><p>キーワードを短くするか、絞り込み条件を減らしてください。</p></div>';
  $('more').hidden=filtered.length<=limit;
 }
 $('stats').innerHTML=`<span><strong>${D.articles.length}</strong>記事</span><span><strong>${D.authors.length}</strong>書き手</span>`;
 const errors=D.status.feeds.filter(f=>f.status==='error').length;
 $('notice').textContent=(D.settings.public_release?'RSSを定期確認。公開日を基準に記事を表示しています。':'確認用サイトです。一般公開・定期更新はまだ開始していません。')+(errors?` 現在 ${errors} 件の取得エラーがあります。既存記事は保持しています。`:'')+(Date.now()-new Date(D.status.attempted_at).getTime()>86400000?' 最終取得から24時間以上経過しています。':'');
 $('updated').textContent=`最終取得：${date(D.status.attempted_at)} ${new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit'}).format(new Date(D.status.attempted_at))} JST`;
 renderAuthors();
 const contact=D.settings.contact_url;const repo=D.settings.repository_url;
 $('contact').innerHTML=contact?`<p><a href="${url(contact)}" target="_blank" rel="noopener">お問い合わせ・掲載取り下げ窓口 ↗</a></p>`:'<p>現在は確認用サイトのため、受付窓口は未開設です。一般公開前に運営者の連絡窓口を設定します。</p>';
 if(repo)$('contact').insertAdjacentHTML('beforeend',`<p><a href="${url(repo+'/issues/new/choose')}" target="_blank" rel="noopener">書き手の推薦・訂正を申請する ↗</a>（GitHubアカウントが必要です。個人情報は記載しないでください。）</p>`);
 $('feed-status').innerHTML=`<p>${D.status.successful_feeds} / ${D.status.total_feeds} フィード取得成功。各記事の公開日はRSS、または手動登録時に確認した日付に基づきます。</p><table class="status-table"><thead><tr><th>書き手</th><th>状態</th><th>最終成功日</th></tr></thead><tbody>${D.status.feeds.map(f=>`<tr><td>${esc(byId[f.id]?.name||f.id)}</td><td>${f.status==='error'?'取得失敗：'+esc(f.error):'取得成功'}</td><td>${date(f.last_success)}</td></tr>`).join('')}</tbody></table>`;
 document.addEventListener('click',e=>{const link=e.target.closest('a.tracked-article');if(!link||typeof window.gtag!=='function')return;const author=byId[link.dataset.authorId];window.gtag('event','article_click',{link_url:link.href,article_title:link.dataset.articleTitle||'',author_id:link.dataset.authorId||'',author_name:author?.name||''});});
 document.addEventListener('click',e=>{const clear=e.target.closest('[data-clear-filter]');if(clear){state[clear.dataset.clearFilter]='';limit=30;sync();save();$('reset').focus();return;}const g=e.target.closest('[data-group]');if(g){state.group=g.dataset.group;state.member='';state.song='';state.view='articles';limit=30;sync();save();document.querySelector('.group-tab.active').focus();return;}const c=e.target.closest('[data-category]');if(c){state.cat=c.dataset.category;state.view='articles';limit=30;save();document.querySelector('.category.active').focus();return;}const nav=e.target.closest('[data-view]');if(nav){e.preventDefault();state.view=nav.dataset.view;save();}});
 $('search-form').addEventListener('submit',e=>{e.preventDefault();state.q=$('query').value;limit=30;save();});
 $('query').addEventListener('input',()=>{state.q=$('query').value;limit=30;render();});
 controls.forEach(id=>$(id).addEventListener('change',()=>{state[id]=$(id).value;if(id==='sort'&&state.sort==='random')reshuffle();limit=30;save();}));
 $('reshuffle').addEventListener('click',()=>{reshuffle();limit=30;render();});
 $('random-essay-trigger').addEventListener('click',drawRandomEssay);
 $('random-essay-next').addEventListener('click',drawRandomEssay);
 $('random-essay-close').addEventListener('click',()=>{
  randomEssay=null;
  renderRandomEssay();
  $('random-essay-trigger').focus();
 });
 $('author-reshuffle').addEventListener('click',()=>{reshuffleAuthors();if(state.view==='authors')renderAuthors();});
 $('author-search-form').addEventListener('submit',e=>e.preventDefault());
 $('author-query').addEventListener('input',()=>{
  writerQuery=$('author-query').value;
  if(state.view==='authors')renderAuthors();
 });
 $('author-clear').addEventListener('click',()=>{
  writerQuery='';
  $('author-query').value='';
  renderAuthors();
  $('author-query').focus();
 });
 $('reset').addEventListener('click',reset);$('more').addEventListener('click',()=>{limit+=30;render();});
 $('past-shortcut').addEventListener('click',()=>{const d=new Date();d.setMonth(d.getMonth()-3);state.to=day(d.toISOString());state.sort='new';state.view='articles';limit=30;sync();save();});
 window.addEventListener('popstate',readState);readState();
})();
