(() => {
  'use strict';
  const state = { model:'pro', storage:'256gb', trust:'all', latest:{variants:{}}, history:{} };
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const euro = (amount) => typeof amount === 'number' ? new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR',maximumFractionDigits:2,minimumFractionDigits:0}).format(amount) : '—';
  const safe = (v) => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const validUrl = (s) => {try { const u=new URL(s);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
  const dateLabel = (date) => date ? new Date(date).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Rome'})+' CET/CEST' : 'Not yet scanned';
  const variant = () => `${state.model==='max'?'pro-max':'pro'}-${state.storage}`;
  const current = () => state.latest.variants?.[variant()] || {};
  const vTitle = () => 'iPhone 17 Pro'+(state.model==='max'?' Max':'')+' · '+state.storage.toUpperCase();
  const showToast = (t) => {const el=$('#toast'); el.textContent=t;el.classList.add('visible');setTimeout(()=>el.classList.remove('visible'),2200);};

  function renderSummary(){
    const hasScan=!!state.latest.checked_at;
    const lastMs=Date.parse(state.latest.checked_at || '');
    const isFresh=hasScan && Number.isFinite(lastMs) && (Date.now()-lastMs)<(150*60*1000);
    $('#last-checked').textContent=dateLabel(state.latest.checked_at);
    $('#footer-updated').textContent='Updated: '+dateLabel(state.latest.checked_at);
    const offers=Object.values(state.latest.variants||{}).reduce((n,v)=>n+(v.offers?.filter(o=>typeof o.price_eur==='number').length||0),0);
    $('#offer-count').textContent=hasScan?`${offers} quoted prices`:'Awaiting scan';
    const pill=$('#run-status');
    pill.classList.toggle('live',isFresh && !state.latest.error_count);
    pill.classList.toggle('error',hasScan && (!isFresh || !!state.latest.error_count));
    pill.textContent=!hasScan?'Awaiting first scan':!isFresh?'Scan overdue':state.latest.error_count?`Partial scan · ${state.latest.error_count} errors`:'Recent scan';
    for(const [id,prefix] of [['pro-256gb','pro'],['pro-max-256gb','max']]){
      const v=state.latest.variants?.[id]; const best=(v?.offers||[]).filter(o=>typeof o.price_eur==='number').sort((a,b)=>a.price_eur-b.price_eur)[0];
      $(`#feature-${prefix}-price`).textContent=best?euro(best.price_eur):'—';
      $(`#feature-${prefix}-seller`).textContent=v?.status==='error'?'Last available result · scan failed':!isFresh&&hasScan?'Last observed price · scan overdue':best?`${best.merchant} · ${best.trust==='trusted_retailer'?'retailer price':'seller needs verification'} · excluding unknown shipping`:hasScan?(v?.offers?.length?'Retailer listings found · check current prices':'No matching retailer pages found'):'Awaiting first scan';
    }
  }
  function renderOffers(){
    $$('[data-model]').forEach(btn=>{const selected=btn.dataset.model===state.model;btn.classList.toggle('selected',selected);btn.setAttribute('aria-pressed',String(selected));});
    $$('[data-trust]').forEach(btn=>{const selected=btn.dataset.trust===state.trust;btn.classList.toggle('selected',selected);btn.setAttribute('aria-pressed',String(selected));});
    $$('#storage option').forEach(opt=>{opt.disabled=state.model==='pro'&&opt.value==='2tb';});
    $('#storage').value=state.storage;
    const v=current(), all=v.offers||[], offers=all.filter(x=>state.trust==='all'||x.trust===state.trust).sort((a,b)=>Number(a.price_eur==null)-Number(b.price_eur==null)||(a.price_eur??0)-(b.price_eur??0)||String(a.merchant).localeCompare(String(b.merchant)));
    $('#view-summary').textContent=`${vTitle()} · ${offers.length} ${state.trust==='all'?'matching':state.trust==='trusted_retailer'?'direct-retailer':state.trust==='unverified_seller'?'unvetted-seller':'seller-check'} result${offers.length!==1?'s':''}${v.status==='error'?' · OUTDATED':''}`;
    $('#view-timestamp').textContent=v.checked_at?'Checked '+dateLabel(v.checked_at):'';
    $('#result-caption').textContent=v.status==='error'?'WARNING: latest scan failed; previous listings are shown for reference only':state.trust==='review_seller'?'Seller or search price requires verification':state.trust==='all'?'Showing all quoted prices (including unvetted sellers); verify seller, condition and shipping':'Some listings require opening the store to see their price';
    if(!offers.length){
      $('#offers-list').innerHTML=`<div class="empty-state">${!state.latest.checked_at?'The monitor has not run yet. Results appear after the first scheduled check.':v.status==='error'?'The latest search failed. No fresh results available.':'No matching offers found in this category. Try a different storage size or seller-quality filter.'}</div>`;
      return;
    }
    $('#offers-list').innerHTML=offers.map((o,i)=>{
      const shipping=o.shipping_eur===0?'Free shipping reported':typeof o.shipping_eur==='number'?`Shipping ${euro(o.shipping_eur)}`:'Shipping not confirmed';
      const link=validUrl(o.link);
      return `<article class="offer-row ${o.trust!=='trusted_retailer'?'review':''}">
        <div class="offer-index ${i===0 && o.price_eur!=null?'best':''}">${i===0 && o.price_eur!=null?'★':i+1}</div>
        <div><div class="offer-name">${safe(o.merchant)}</div><div class="offer-desc" title="${safe(o.title)}">${safe(o.title)}</div></div>
        <div class="offer-merchant">${v.status==='error'?'Stale listing — not live':o.price_status==='check_on_store'?'Official store page · check price':o.trust==='unverified_seller'?'UNVETTED SELLER · verify independently':o.price_status==='search_snippet_unverified'?'Search price · verify checkout':o.trust==='review_seller'?'Marketplace / seller to verify':o.price_status==='retailer_structured_price'?'Retailer page price · verify checkout':'Retailer listing · verify checkout'}<small>${shipping}</small></div>
        <div class="offer-price">${o.price_eur==null?'Check price':euro(o.price_eur)}<small>${o.price_status==='search_snippet_unverified'||o.price_status==='shopping_listing'?'Shopping/search quote':o.price_eur==null?'Open retailer page':'Retailer-advertised price'}</small></div>
        <a class="offer-link" href="${safe(link)}" target="_blank" rel="noopener noreferrer">Check listing ↗</a>
      </article>`;
    }).join('');
  }
  function renderChart(){
    $('#chart-name').textContent=vTitle();
    const points=(state.history[variant()]||[]).filter(x=>typeof x.price_eur==='number').slice(-240);
    if(points.length===0){$('#chart-detail').textContent='No observations yet';$('#chart').innerHTML='<div class="chart-empty">Price history begins with the first hourly check.</div>';return;}
    const prices=points.map(x=>x.price_eur), min=Math.min(...prices), max=Math.max(...prices), spread=Math.max(max-min,30);
    $('#chart-detail').textContent=`${points.length} observations · low ${euro(min)} · current ${euro(prices.at(-1))}`;
    const W=1000,H=240,l=77,r=18,t=20,b=35,lo=Math.max(0,min-spread*.22),hi=max+spread*.25;
    const x=i=>l+(W-l-r)*(points.length===1?.5:i/(points.length-1)), y=p=>H-b-(p-lo)/(hi-lo)*(H-t-b);
    const path=points.map((p,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(p.price_eur).toFixed(1)}`).join(' ');
    const area=`${path} L${x(points.length-1)},${H-b} L${x(0)},${H-b} Z`;
    let lines='';for(let i=0;i<=3;i++){const value=lo+(hi-lo)*i/3,Y=y(value);lines+=`<line x1="${l}" y1="${Y}" x2="${W-r}" y2="${Y}" stroke="#344151" stroke-dasharray="4 6"/><text x="${l-12}" y="${Y+4}" fill="#8190a1" text-anchor="end" font-size="12">€${Math.round(value)}</text>`;}
    const ticks=[0,Math.floor((points.length-1)/2),points.length-1].filter((n,i,a)=>a.indexOf(n)===i).map(n=>`<text x="${x(n)}" y="${H-7}" text-anchor="middle" fill="#8290a1" font-size="12">${safe(new Date(points[n].at).toLocaleDateString('en-GB',{day:'2-digit',month:'short',timeZone:'Europe/Rome'}))}</text>`).join('');
    const dotx=x(points.length-1), doty=y(prices.at(-1));
    $('#chart').innerHTML=`<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Price history, lowest approved-retailer price ${euro(min)}">
      <defs><linearGradient id="pricefill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#95ddb6" stop-opacity=".26"/><stop offset="100%" stop-color="#95ddb6" stop-opacity="0"/></linearGradient></defs>
      ${lines}<path d="${area}" fill="url(#pricefill)"/><path d="${path}" stroke="#a2e9c7" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" fill="none"/><circle cx="${dotx}" cy="${doty}" r="6" fill="#b5f2d4" stroke="#17231f" stroke-width="3"/>${ticks}</svg>`;
  }
  function render(){renderSummary();renderOffers();renderChart();}
  $$('[data-model]').forEach(btn=>btn.addEventListener('click',()=>{state.model=btn.dataset.model;if(state.model==='pro'&&state.storage==='2tb')state.storage='1tb';render();}));
  $$('[data-trust]').forEach(btn=>btn.addEventListener('click',()=>{state.trust=btn.dataset.trust;render();}));
  $('#storage').addEventListener('change',e=>{state.storage=e.target.value;render();});
  $$('.choose-model').forEach(btn=>btn.addEventListener('click',()=>{state.model=btn.dataset.model;state.storage=btn.dataset.storage;state.trust='all';render();$('#offers').scrollIntoView({behavior:'smooth',block:'start'});}));
  $('#share-button').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(location.href);showToast('Dashboard link copied');}
    catch{showToast('Copy this page URL from your browser');}
  });
  $('#whatsapp-link').href='https://wa.me/?text='+encodeURIComponent('iPhone price tracking in Italy — live dashboard: '+location.href);
  function refreshPrices(){
    return Promise.all([
      fetch('./data/latest.json?cache='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Cannot load prices');return r.json();}),
      fetch('./data/history.json?cache='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{})
    ]).then(([latest,history])=>{state.latest=latest;state.history=history;render();})
      .catch(()=>{render();$('#run-status').textContent='Data unavailable';$('#run-status').classList.add('error');});
  }
  refreshPrices();
  setInterval(refreshPrices,5*60*1000);
})();
