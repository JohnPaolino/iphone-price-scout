// Minimal browser-free runtime smoke test. Catches rendering exceptions that
// a syntax-only check misses (e.g. calling .forEach on querySelector()).
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const state = new Map();
function element(id) {
  if (!state.has(id)) {
    state.set(id, {
      dataset: {}, value: '', textContent: '', innerHTML: '',
      classList: {toggle(){},add(){},remove(){}},
      addEventListener(){}, setAttribute(){}, scrollIntoView(){}
    });
  }
  return state.get(id);
}
const models = ['all','pro','max'].map(m => Object.assign(element('button:'+m), {dataset:{model:m}}));
const storage = ['all','256gb','512gb','1tb','2tb'].map(x => Object.assign(element('option:'+x), {value:x}));
const latest = {
  checked_at:'2026-11-20T12:00:00Z',error_count:0,variants:{
    'pro-256gb':{status:'ok',checked_at:'2026-11-20T12:00:00Z',offers:[
      {model:'Pro',storage:'256GB',merchant:'Unieuro',title:'iPhone 17 Pro 256GB',
        price_eur:1179,trust:'trusted_retailer',link:'https://www.unieuro.it/pro'},
      {model:'Pro',storage:'256GB',merchant:'Sample Marketplace',title:'iPhone 17 Pro 256GB',
        price_eur:1099,trust:'unverified_seller',link:'https://www.google.com/shopping/product/123'}
    ]},
    'pro-max-256gb':{status:'ok',checked_at:'2026-11-20T12:00:00Z',offers:[
      {model:'Pro Max',storage:'256GB',merchant:'Amazon.it',title:'iPhone 17 Pro Max 256GB',
        price_eur:null,trust:'review_seller',link:'https://www.amazon.it/dp/example'}
    ]}
  }
};
const document = {
  querySelector: element,
  querySelectorAll(selector){
    if(selector==='[data-model]') return models;
    if(selector==='#storage option') return storage;
    if(selector==='[data-trust]') return [];
    if(selector==='.choose-model') return [];
    return [];
  }
};
const ctx = {
  document, console, URL, Date, Intl, Promise,
  setTimeout(){}, setInterval(){},
  location:{href:'https://example.github.io/iphone-price-scout/'},
  navigator:{clipboard:{writeText:async()=>{}}},
  fetch:async (url)=>({ok:true,json:async()=>String(url).includes('latest.json')?latest:{}})
};
vm.runInNewContext(fs.readFileSync('docs/app.js','utf8'),ctx,{filename:'docs/app.js'});
(async ()=>{
  for(let i=0;i<12;i++)await Promise.resolve();
  const recognized=element('#offers-list').innerHTML;
  const unvetted=element('#unvetted-list').innerHTML;
  assert.match(recognized,/Unieuro/);
  assert.match(recognized,/1\.179/);
  assert.match(unvetted,/Sample Marketplace/);
  assert.match(unvetted,/Amazon\.it/);
  assert.match(element('#offer-count').textContent,/2 quoted prices/);
  console.log('Dashboard smoke test passed: priced offers and Amazon links visible');
})().catch(e=>{console.error(e);process.exitCode=1;});
