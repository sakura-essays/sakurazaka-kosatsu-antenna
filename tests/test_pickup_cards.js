'use strict';
// Execute the real application with a small DOM double; no test data reaches dist.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const app=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
function run(articles,pickups,search=''){
 const elements=new Map(),events={};
 const element=id=>{
  if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:false,value:'',open:false,events:{},attrs:{},insertAdjacentHTML(_,s){this.innerHTML+=s;},addEventListener(k,f){this.events[k]=f;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},getAttribute(k){return this.attrs[k]??null;},focus(){}});
  return elements.get(id);
 };
 const authors=[...new Set(articles.map(a=>a.author_id))].map(id=>({id,name:id==='writer'?'書き手 <A> & "B"':id,platform:'note',url:'https://note.com/'+id,count:articles.filter(a=>a.author_id===id).length,themes:[]}));
 const document={baseURI:'https://example.test/',getElementById:element,querySelector:()=>element('filters'),querySelectorAll:()=>[],addEventListener(k,f){(events[k]??=[]).push(f);}};
 const location={search};
 const context={document,location,history:{pushState(_,__,s){location.search=s;}},URL,URLSearchParams,Intl,Date,Math,window:{ANTENNA:{articles,authors,pickups,groups:['乃木坂46','櫻坂46','日向坂46'],categories:['楽曲・歌詞考察'],settings:{public_release:true},status:{feeds:[],attempted_at:new Date().toISOString(),successful_feeds:0,total_feeds:0}},addEventListener(){}}};
 vm.runInNewContext(app.replace(" window.addEventListener('popstate'", " window.__testRelated=relatedArticles; window.__testFeatures=relationFeatures;\n window.addEventListener('popstate'"),context);
 return {element,related:a=>context.window.__testRelated(a),features:context.window.__testFeatures,html:()=>element('pickup-list').innerHTML,clickButton(id){const el=element(id);assert.equal(typeof el.events.click,'function',id+' click listener');el.events.click();},clickGroup(group){for(const f of events.click)f({target:{closest(selector){return selector==='[data-group]'?{dataset:{group}}:null;}}});}};
}
const article=(id,groups,categories=['楽曲・歌詞考察'],title='元のタイトル')=>({id,url:'https://note.com/writer/n/'+id,title,author_id:'writer',published_at:'2026-01-01T00:00:00Z',groups,categories,members:[],songs:[]});
const cases=[['乃木坂46','nogi'],['櫻坂46','sakura'],['日向坂46','hinata']];
for(const [group,tone] of cases){
 const a=article(tone,[group]),r=run([a],[{url:a.url,note:'既存の推薦理由'}]);
 assert.equal(r.element('pickup-section').hidden,false);
 assert.ok(r.html().includes('pickup-tone-'+tone));
 assert.ok(r.html().includes(group));
 assert.ok(r.html().includes('pickup-theme-music'));
 assert.ok(r.html().includes('aria-hidden="true"'));
 assert.ok(r.html().includes('href="'+a.url+'"'));
 assert.match(r.html(),/<a class="pickup-link tracked-article" aria-labelledby="([^"]+)"/);
 assert.ok(r.html().includes('既存の推薦理由'));
 assert.doesNotMatch(r.html(),/<(?:img|svg|canvas|video|picture)\b/);
 assert.equal((r.html().match(/<a\b/g)||[]).length,1,'one keyboard stop for the whole card');
}
for(const [category,theme] of [
 ['メンバー考察・人物論','person'],['楽曲・歌詞考察','music'],
 ['ダンス・パフォーマンス考察','performance'],['ライブ・コンサート','live'],
 ['そこ曲がったら、櫻坂？','program'],['乃木坂工事中','program'],
 ['日向坂で会いましょう','program'],['グループ運営・アイドル論','group']]){
 const a=article(theme,['櫻坂46'],[category]);
 assert.ok(run([a],[{url:a.url,note:'理由'}]).html().includes('pickup-theme-'+theme));
}
const mixed=article('mixed',['乃木坂46','日向坂46']);
assert.ok(run([mixed],[{url:mixed.url,note:'比較'}]).html().includes('pickup-tone-neutral'));
const malicious=article('safeid',['櫻坂46'],['メンバー考察・人物論'],'長い原題<&"\'>'+('とても長いタイトル'.repeat(25)));
const r=run([malicious],[{url:malicious.url,note:'推薦理由 <script> & "引用"'}]);
assert.ok(r.html().includes('pickup-theme-person'));
assert.ok(r.html().includes('長い原題&lt;&amp;&quot;&#39;&gt;'));
assert.ok(r.html().includes('とても長いタイトル'.repeat(25)),'full original title is preserved');
assert.ok(r.html().includes('推薦理由 &lt;script&gt; &amp; &quot;引用&quot;'));
assert.ok(r.html().includes('書き手 &lt;A&gt; &amp; &quot;B&quot;'));
assert.doesNotMatch(r.html(),/<script>/);
assert.equal(run([malicious],[]).element('pickup-section').hidden,true);
assert.equal(run([malicious],[]).html(),'');
const a=article('one',['乃木坂46']),b=article('two',['日向坂46']);
const filtered=run([a,b,mixed],[a,b,mixed].map(a=>({url:a.url,note:'記録'})));
filtered.clickGroup('日向坂46');
assert.ok(!filtered.html().includes('pickup-tone-nogi'));
assert.ok(filtered.html().includes('pickup-tone-hinata'));
assert.ok(filtered.html().includes('pickup-tone-neutral'));
assert.equal(run([a],[{url:a.url,note:'記録'}],'?q=元のタイトル').element('pickup-section').hidden,true,'search retains its existing behavior');
// The archive draw is opt-in, and should not compete with the latest feed by default.
const archive=article('archived',['櫻坂46']);
const optIn=run([archive],[]);
assert.equal(optIn.element('random-essay').hidden,true,'the archive card starts hidden');
assert.equal(optIn.element('random-essay-trigger').hidden,false);
optIn.clickButton('random-essay-trigger');
assert.equal(optIn.element('random-essay').hidden,false,'clicking reveals one article');
assert.match(optIn.element('random-essay-body').innerHTML,/元のタイトル/);
assert.equal(optIn.element('random-essay-trigger').getAttribute('aria-expanded'),'true');
optIn.clickButton('random-essay-close');
assert.equal(optIn.element('random-essay').hidden,true,'the user can dismiss the card');
assert.equal(optIn.element('random-essay-trigger').getAttribute('aria-expanded'),'false');
const recentlyPublished={...archive,published_at:new Date().toISOString()};
assert.equal(run([recentlyPublished],[]).element('random-essay-trigger').hidden,true,'only old articles are drawn');
assert.equal(run([archive],[{url:archive.url,note:'already curated'}]).element('random-essay-trigger').hidden,true,'curated picks do not get repeated');
const groupOnly=run([archive],[]);
groupOnly.clickGroup('乃木坂46');
assert.equal(groupOnly.element('random-essay-trigger').hidden,true,'group filters are respected');
groupOnly.clickGroup('櫻坂46');
assert.equal(groupOnly.element('random-essay-trigger').hidden,false);
const w1=article('first',['櫻坂46'],['楽曲・歌詞考察'],'Writer 1');
const w2={...article('second',['櫻坂46'],['楽曲・歌詞考察'],'Writer 2'),author_id:'other'};
const writers=run([w1,w2],[]);
writers.clickButton('random-essay-trigger');
const first=writers.element('random-essay-body').innerHTML;
writers.clickButton('random-essay-next');
const second=writers.element('random-essay-body').innerHTML;
assert.notEqual(first,second,'draws avoid immediately repeating the same author');
// Writer search combines group badges, names and public IDs.
const writerArticles=[
 {...article('nogi-post',['乃木坂46']),author_id:'nogi'},
 {...article('sakura-post',['櫻坂46']),author_id:'sakura'},
 {...article('hinata-post',['日向坂46']),author_id:'hinata'},
 {...article('mixed-post',['櫻坂46','日向坂46']),author_id:'mixed'}
];
const writerSearch=run(writerArticles,[],'?view=authors');
function searchWriters(query){
 const field=writerSearch.element('author-query');
 field.value=query;
 field.events.input();
 const html=writerSearch.element('authors-grid').innerHTML;
 return [...html.matchAll(/<h3><a [^>]*>([^<]*)<\/a><\/h3>/g)].map(m=>m[1]).sort();
}
assert.deepEqual(searchWriters('乃木坂46'),['nogi']);
assert.deepEqual(searchWriters('櫻坂46'),['mixed','sakura']);
assert.deepEqual(searchWriters('日向坂46'),['hinata','mixed']);
assert.deepEqual(searchWriters('欅坂46'),['mixed','sakura'],'historic Keyakizaka alias');
assert.deepEqual(searchWriters('櫻坂46 mixed'),['mixed'],'combined group and writer search');
assert.deepEqual(searchWriters('sakura'),['sakura'],'name and ID search remain supported');
assert.deepEqual(searchWriters('不在のグループ'),[],'unmatched groups filter cleanly');
writerSearch.clickButton('author-clear');
assert.equal(writerSearch.element('author-result-count').textContent,'4人の書き手');
const css=fs.readFileSync(path.join(__dirname,'../web/style.css'),'utf8');
assert.doesNotMatch(css,/url\s*\(/i,'no external image or font assets');
assert.match(css,/aspect-ratio:16\/9/);
assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
console.log('Pickup cards + random archive: render, colors, escaping, opt-in, dates, category groups, close, author fairness: passed');

module.exports={run,article};
