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
 function reshuffle(){const items=[...D.articles];for(let i=items.length-1;i>0;i--){const k=Math.floor(Math.random()*(i+1));[items[i],items[k]]=[items[k],items[i]];}randomRanks=new Map(items.map((a,i)=>[a.url,i]));}
 reshuffle();
 const controls=['author','member','song','platform','from','to','sort'];
 const articleGroups=a=>a.groups?.length?a.groups:['櫻坂46'];
 const inGroup=a=>!state.group||articleGroups(a).includes(state.group);
 const allGroups=D.groups||['乃木坂46','櫻坂46','日向坂46'];
 const articlesByUrl=new Map(D.articles.map(a=>[a.url,a]));
 const picks=(D.pickups||[]).map(p=>({article:articlesByUrl.get(p.url),note:p.note})).filter(p=>p.article&&byId[p.article.author_id]);
 for(let i=picks.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[picks[i],picks[j]]=[picks[j],picks[i]];}
 function renderPickups(){
  const block=$('pickup-section');
  const narrowed=state.q||state.cat||state.author||state.member||state.song||state.platform||state.from||state.to;
  const visible=narrowed?[]:picks.filter(p=>inGroup(p.article));
  block.hidden=!visible.length;
  if(!visible.length){$('pickup-list').innerHTML='';return;}
  $('pickup-list').innerHTML=visible.map(({article:a,note})=>{
   const w=byId[a.author_id];
   return `<article class="pickup-card"><div class="group-labels">${articleGroups(a).map(g=>`<span class="group-label">${esc(g)}</span>`).join('')}</div><h3><a class="tracked-article" data-author-id="${esc(a.author_id)}" data-article-title="${esc(a.title)}" href="${url(a.url)}" target="_blank" rel="noopener">${esc(a.title)}<span class="sr-only">（元記事を新しいタブで開く）</span></a></h3><p class="pickup-author">${esc(w.name)}</p><p class="pickup-reason">${esc(note)}</p></article>`;
  }).join('');
 }
 function options(id,items){$(id).insertAdjacentHTML('beforeend',items.map(([v,l])=>`<option value="${esc(v)}">${esc(l)}</option>`).join(''));}
 options('author',D.authors.map(a=>[a.id,a.name]));
 for(const [id,field] of [['member','members'],['song','songs']])options(id,[...new Set(D.articles.flatMap(a=>a[field]))].sort((a,b)=>a.localeCompare(b,'ja')).map(x=>[x,x]));
 function readState(){const p=new URLSearchParams(location.search);state={view:p.get('view')||'articles',group:allGroups.includes(p.get('group'))?p.get('group'):'',q:p.get('q')||'',cat:p.get('cat')||'',author:p.has('author')?p.get('author'):(window.PRESET_AUTHOR||''),member:p.get('member')||'',song:p.get('song')||'',platform:p.get('platform')||'',from:p.get('from')||'',to:p.get('to')||'',sort:p.get('sort')||'new'};if(!['articles','authors','about'].includes(state.view))state.view='articles';limit=30;sync();render();}
 function sync(){ $('query').value=state.q;controls.forEach(id=>$(id).value=state[id]);if(controls.some(k=>k!=='sort'&&state[k]))document.querySelector('.filters').open=true;}
 function save(){const p=new URLSearchParams();Object.entries(state).forEach(([k,v])=>{if(v)p.set(k,v)});if(window.PRESET_AUTHOR&&!state.author)p.set('author','');history.pushState(null,'','?'+p.toString());render();}
 function reset(){state={view:'articles',group:'',q:'',cat:'',author:'',member:'',song:'',platform:'',from:'',to:'',sort:'new'};limit=30;sync();save();}
 function card(a){const w=byId[a.author_id];return `<article class="article"><div class="article-top"><time datetime="${esc(a.published_at)}">${date(a.published_at)}</time><span class="group-labels">${articleGroups(a).map(g=>`<span class="group-label">${esc(g)}</span>`).join('')}</span><span class="platform">${esc(w.platform)}</span></div><h3><a class="tracked-article" data-author-id="${esc(a.author_id)}" data-article-title="${esc(a.title)}" href="${url(a.url)}" target="_blank" rel="noopener">${esc(a.title)}<span class="external" aria-hidden="true">↗</span><span class="sr-only">（元記事を新しいタブで開く）</span></a></h3><div class="article-bottom"><a class="author-link" href="${esc(authorPath(w.id))}">${esc(w.name)}</a><div class="tags">${a.categories.map(c=>`<button class="tag" data-category="${esc(c)}">${esc(c)}</button>`).join('')}</div></div></article>`;}
 function balanced(items){const buckets=new Map();for(const a of items){if(!buckets.has(a.author_id))buckets.set(a.author_id,[]);buckets.get(a.author_id).push(a);}const out=[];let more=true;while(more){more=false;for(const bucket of buckets.values()){if(bucket.length){out.push(bucket.shift());more=true}}}return out;}
 function render(){
  document.querySelectorAll('[data-view]').forEach(a=>{a.classList.toggle('active',a.dataset.view===state.view);if(a.dataset.view===state.view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('article-view').hidden=state.view!=='articles';$('authors-view').hidden=state.view!=='authors';$('about-view').hidden=state.view!=='about';
  if(state.view==='authors'){$('authors-grid').innerHTML=D.authors.filter(a=>!state.group||D.articles.some(x=>x.author_id===a.id&&inGroup(x))).map(a=>`<article class="writer-card"><span class="platform">${esc(a.platform)}</span><h3><a href="${esc(authorPath(a.id))}">${esc(a.name)}</a></h3><p class="count">収集済み ${a.count} 記事</p><p class="themes">${esc(a.themes.join(' / '))}</p><div class="writer-bottom"><a href="${esc(authorPath(a.id))}">記事一覧へ →</a><a href="${url(a.url)}" target="_blank" rel="noopener">元サイト ↗</a></div></article>`).join('');return;}
  if(state.view!=='articles')return;
  $('group-tabs').innerHTML=[['','すべて'],...allGroups.map(g=>[g,g])].map(([g,label])=>`<button type="button" class="group-tab ${state.group===g?'active':''}" data-group="${esc(g)}" aria-pressed="${state.group===g}">${esc(label)}<span class="num">${D.articles.filter(a=>!g||articleGroups(a).includes(g)).length}</span></button>`).join('');
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
  $('result-count').textContent=`${filtered.length} 件${filtered.length>limit?` / ${limit} 件を表示`:''}`;
  $('articles').innerHTML=filtered.length?filtered.slice(0,limit).map(card).join(''):'<div class="empty"><p>この条件に合う記事はまだありません。</p><p>キーワードを短くするか、絞り込み条件を減らしてください。</p></div>';
  $('more').hidden=filtered.length<=limit;
 }
 $('stats').innerHTML=`<span><strong>${D.articles.length}</strong>記事</span><span><strong>${D.authors.length}</strong>書き手</span>`;
 const errors=D.status.feeds.filter(f=>f.status==='error').length;
 $('notice').textContent=(D.settings.public_release?'RSSを定期確認。公開日を基準に記事を表示しています。':'確認用サイトです。一般公開・定期更新はまだ開始していません。')+(errors?` 現在 ${errors} 件の取得エラーがあります。既存記事は保持しています。`:'')+(Date.now()-new Date(D.status.attempted_at).getTime()>86400000?' 最終取得から24時間以上経過しています。':'');
 $('updated').textContent=`最終取得：${date(D.status.attempted_at)} ${new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit'}).format(new Date(D.status.attempted_at))} JST`;
 $('authors-grid').innerHTML=D.authors.filter(a=>!state.group||D.articles.some(x=>x.author_id===a.id&&inGroup(x))).map(a=>`<article class="writer-card"><span class="platform">${esc(a.platform)}</span><h3><a href="${esc(authorPath(a.id))}">${esc(a.name)}</a></h3><p class="count">収集済み ${a.count} 記事</p><p class="themes">${esc(a.themes.join(' / '))}</p><div class="writer-bottom"><a href="${esc(authorPath(a.id))}">記事一覧へ →</a><a href="${url(a.url)}" target="_blank" rel="noopener">元サイト ↗</a></div></article>`).join('');
 const contact=D.settings.contact_url;const repo=D.settings.repository_url;
 $('contact').innerHTML=contact?`<p><a href="${url(contact)}" target="_blank" rel="noopener">お問い合わせ・掲載取り下げ窓口 ↗</a></p>`:'<p>現在は確認用サイトのため、受付窓口は未開設です。一般公開前に運営者の連絡窓口を設定します。</p>';
 if(repo)$('contact').insertAdjacentHTML('beforeend',`<p><a href="${url(repo+'/issues/new/choose')}" target="_blank" rel="noopener">書き手の推薦・訂正を申請する ↗</a>（GitHubアカウントが必要です。個人情報は記載しないでください。）</p>`);
 $('feed-status').innerHTML=`<p>${D.status.successful_feeds} / ${D.status.total_feeds} フィード取得成功。各記事の公開日はRSS、または手動登録時に確認した日付に基づきます。</p><table class="status-table"><thead><tr><th>書き手</th><th>状態</th><th>最終成功日</th></tr></thead><tbody>${D.status.feeds.map(f=>`<tr><td>${esc(byId[f.id]?.name||f.id)}</td><td>${f.status==='error'?'取得失敗：'+esc(f.error):'取得成功'}</td><td>${date(f.last_success)}</td></tr>`).join('')}</tbody></table>`;
 document.addEventListener('click',e=>{const link=e.target.closest('a.tracked-article');if(!link||typeof window.gtag!=='function')return;const author=byId[link.dataset.authorId];window.gtag('event','article_click',{link_url:link.href,article_title:link.dataset.articleTitle||'',author_id:link.dataset.authorId||'',author_name:author?.name||''});});
 document.addEventListener('click',e=>{const g=e.target.closest('[data-group]');if(g){state.group=g.dataset.group;state.member='';state.song='';state.view='articles';limit=30;sync();save();return;}const c=e.target.closest('[data-category]');if(c){state.cat=c.dataset.category;state.view='articles';limit=30;save();return;}const nav=e.target.closest('[data-view]');if(nav){e.preventDefault();state.view=nav.dataset.view;save();}});
 $('search-form').addEventListener('submit',e=>{e.preventDefault();state.q=$('query').value;limit=30;save();});
 $('query').addEventListener('input',()=>{state.q=$('query').value;limit=30;render();});
 controls.forEach(id=>$(id).addEventListener('change',()=>{state[id]=$(id).value;if(id==='sort'&&state.sort==='random')reshuffle();limit=30;save();}));
 $('reshuffle').addEventListener('click',()=>{reshuffle();limit=30;render();});
 $('reset').addEventListener('click',reset);$('more').addEventListener('click',()=>{limit+=30;render();});
 $('past-shortcut').addEventListener('click',()=>{const d=new Date();d.setMonth(d.getMonth()-3);state.to=day(d.toISOString());state.sort='new';state.view='articles';limit=30;sync();save();});
 window.addEventListener('popstate',readState);readState();
})();
