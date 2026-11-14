'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/analytics.js'),'utf8');
const base='https://sakura-essays.github.io/sakurazaka-kosatsu-antenna/';
function run(url=base,storage=new Map(),webdriver=false){
 const listeners={},scripts=[],timers=new Map();let clock=0,observer;
 const doc={readyState:'loading',visibilityState:'visible',title:'アンテナ',referrer:'https://note.com/?private=secret',body:null,head:{appendChild(s){scripts.push(s);}},createElement(){return {};},querySelectorAll(){return [];},addEventListener(k,f){(listeners[k]??=[]).push(f);}};
 const win={ANTENNA:{articles:[{id:'article1',url:'https://note.com/one/n/test',title:'元の記事',author_id:'one',groups:['櫻坂46']}],authors:[{id:'one',name:'書き手'}]}};
 const ctx={window:win,document:doc,location:new URL(url),localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},navigator:{webdriver},URL,Date,setTimeout(f){timers.set(++clock,f);return clock;},clearTimeout(id){timers.delete(id);},IntersectionObserver:class {constructor(f){observer=f;}disconnect(){}observe(){}}};
 vm.runInNewContext(source,ctx);
 return {api:win.AntennaAnalytics,win,scripts,storage,emit(k,e={}){for(const f of listeners[k]||[])f(e);},tick(){const t=[...timers.values()];timers.clear();t.forEach(f=>f());},intersect(link,visible=true){observer([{target:link,isIntersecting:visible,intersectionRatio:visible?1:0}]);}};
}
const r=run();r.api.update({view:'articles',sort:'new'},10);r.emit('DOMContentLoaded');
assert.equal(r.scripts.length,1);const commands=r.win.dataLayer.map(a=>Array.from(a));
assert.equal(commands[1][0],'config');assert.equal(commands[1][2].send_page_view,false);
assert.equal(commands.filter(x=>x[0]==='event'&&x[1]==='page_view').length,1);
r.api.update({view:'articles',group:'櫻坂46',sort:'new'},4);r.api.update({view:'authors',sort:'new'},2);
assert.equal(r.win.dataLayer.filter(x=>x[1]==='page_view').length,1,'filter/view changes never emit PV');
const test=run(base+'?analytics=test&q=private@example.com');test.emit('DOMContentLoaded');
assert.equal(test.scripts.length,0,'test mode sends nothing to Google');
test.api.update({view:'articles',q:'藤吉夏鈴',sort:'new'},0);test.tick();test.api.flushSearch();
assert.equal(test.api.events.filter(x=>x.event==='view_search_results').length,1,'debounce + submit does not duplicate search');
assert.equal(test.api.events.at(-1).zero_results,'true');
test.api.update({view:'articles',q:'森田ひかる',sort:'new'},3);
const link={href:'https://note.com/one/n/test',textContent:'元の記事',dataset:{},isConnected:true,closest(s){return s==='#pickup-list'?{}:null;}};
test.emit('click',{type:'click',button:0,target:{closest:()=>link}});
const click=test.api.events.at(-1);assert.equal(click.event,'article_click');assert.equal(click.placement,'pickup');assert.equal(click.author_name,'書き手');assert.equal(click.article_id,'article1');assert.equal(click.search_term,'森田ひかる');
assert.equal(test.api.events.at(-2).event,'view_search_results','fast click flushes pending search first');
assert.ok(test.api.events.every(x=>!x.page_location.includes('private')),'raw URL query is never sent');
test.api.update({view:'authors',sort:'new'},1,'user@example.com');test.api.flushSearch();assert.equal(test.api.events.at(-1).event,'writer_search');assert.equal(test.api.events.at(-1).search_term,'[redacted]');
test.intersect(link);test.tick();test.intersect(link);test.tick();assert.equal(test.api.events.filter(x=>x.event==='article_impression').length,1,'impression counts once per visible context');
test.emit('auxclick',{type:'auxclick',button:1,target:{closest:()=>link}});assert.equal(test.api.events.at(-1).open_method,'middle');
const storage=new Map();const off=run(base+'?analytics=off',storage);off.emit('DOMContentLoaded');assert.equal(off.scripts.length,0);assert.equal(run(base,storage).api.enabled,false,'opt out persists across pages');
assert.equal(run(base+'?analytics=on',storage).api.enabled,true);
for(const u of ['https://mirror.github.io/sakurazaka-kosatsu-antenna/','http://localhost:8000/','https://sakura-essays.github.io/other/']){const x=run(u);x.emit('DOMContentLoaded');assert.equal(x.scripts.length,0,'no production tag on '+u);}
assert.equal(run(base,new Map(),true).api.enabled,false,'automated verification is excluded');
console.log('Analytics behavior: bootstrap, physical PV, opt-out, host guard, search, privacy, placements, impressions and middle clicks passed');
