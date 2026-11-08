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
  if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:false,value:'',open:false,events:{},insertAdjacentHTML(_,s){this.innerHTML+=s;},addEventListener(k,f){this.events[k]=f;}});
  return elements.get(id);
 };
 const authors=[{id:'writer',name:'書き手 <A> & "B"',platform:'note',url:'https://note.com/writer',count:articles.length,themes:[]}];
 const document={baseURI:'https://example.test/',getElementById:element,querySelector:()=>element('filters'),querySelectorAll:()=>[],addEventListener(k,f){(events[k]??=[]).push(f);}};
 const location={search};
 const context={document,location,history:{pushState(_,__,s){location.search=s;}},URL,URLSearchParams,Intl,Date,Math,window:{ANTENNA:{articles,authors,pickups,groups:['乃木坂46','櫻坂46','日向坂46'],categories:['楽曲・歌詞考察'],settings:{public_release:true},status:{feeds:[],attempted_at:new Date().toISOString(),successful_feeds:0,total_feeds:0}},addEventListener(){}}};
 vm.runInNewContext(app,context);
 return {element,html:()=>element('pickup-list').innerHTML,clickGroup(group){for(const f of events.click)f({target:{closest(selector){return selector==='[data-group]'?{dataset:{group}}:null;}}});}};
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
const css=fs.readFileSync(path.join(__dirname,'../web/style.css'),'utf8');
assert.doesNotMatch(css,/url\s*\(/i,'no external image or font assets');
assert.match(css,/aspect-ratio:16\/9/);
assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
console.log('Pickup cards: palettes, mixed groups, original titles, escaping, links, filters, empty state, no images: passed');
