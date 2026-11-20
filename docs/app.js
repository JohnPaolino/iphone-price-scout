(() => {
  'use strict';
  const state = { model:'pro', storage:'256gb', trust:'trusted_retailer', latest:{variants:{}}, history:{} };
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
    const offers=Object.values(state.latest.variants||{}).reduce((n,v)=>n+(v.offers?.length||0),0);
    $('#offer-count').textContent=hasScan?`${offers} approved-source listings`:'Awaiting scan';
    const pill=$('#run-status');
    pill.classList.toggle('live',isFresh && !state.latest.error_count);
    pill.classList.toggle('error',hasScan && (!isFresh || !!state.latest.error_count));
    pill.textContent=!hasScan?'Awaiting first scan':!isFresh?'Scan overdue':state.latest.error_count?`Partial scan · ${state.latest.error_count} errors`:'Recent scan';
    for(const [id,prefix] of [['pro-256gb','pro'],['pro-max-256gb','max']]){
      const v=state.latest.variants?.[id]; const best=v?.best_trusted;
      $(`#feature-${prefix}-price`).textContent=best?euro(best.price_eur):'—';
      $(`#feature-${prefix}-seller`).textContent=v?.status==='error'?'Last available result · scan failed':!isFresh&&hasScan?'Last observed price · scan overdue':best?`${best.merchant} · ${v.offers.length} listings · delivery may be extra`:hasScan?'No approved retailer found':'Awaiting first scan';
    }
  }
  function renderOffers(){
    $$('[data-model]').forEach(btn=>{const selected=btn.dataset.model===state.model;btn.classList.toggle('selected',selected);btn.setAttribute('aria-pressed',String(selected));});
    $$('[data-trust]').forEach(btn=>{const selected=btn.dataset.trust===state.trust;btn.classList.toggle('selected',selected);btn.setAttribute('aria-pressed',String(selected));});
    $$('#storage option').forEach(opt=>{opt.disabled=state.model==='pro'&&opt.value==='2tb';});
    $('#storage').value=state.storage;
    const v=current(), all=v.offers||[], offers=all.filter(x=>x.trust===state.trust).sort((a,b)=>a.price_eur-b.price_eur);
    $('#view-summary').textContent=`${vTitle()} · ${offers.length} ${state.trust==='review_seller'?'seller-review':'approved-retailer'} result${offers.length!==1?'s':''}${v.status==='error'?' · OUTDATED':''}`;
    $('#view-timestamp').textContent=v.checked_at?'Checked '+dateLabel(v.checked_at):'';
    $('#result-caption').textContent=v.status==='error'?'WARNING: latest scan failed; previous listings are shown for reference only':state.trust==='review_seller'?'Marketplace listings: third-party seller not verified':'Prices shown before unverified delivery charges';
    if(!offers.length){
      $('#offers-list').innerHTML=`<div class="empty-state">${!state.latest.checked_at?'The monitor has not run yet. Results appear after the first scheduled check.':v.status==='error'?'The latest search failed. No fresh results available.':'No matching offers found in this category. Try a different storage size or seller-quality filter.'}</div>`;
      return;
    }
    $('#offers-list').innerHTML=offers.map((o,i)=>{
      const shipping=o.shipping_eur===0?'Free shipping reported':typeof o.shipping_eur==='number'?`Shipping ${euro(o.shipping_eur)}`:'Shipping not confirmed';
      const link=validUrl(o.link);
      return `<article class="offer-row ${state.trust==='review_seller'?'review':''}">
        <div class="offer-index ${i===0?'best':''}">${i===0?'★':i+1}</div>
        <div><div class="offer-name">${safe(o.merchant)}</div><div class="offer-desc" title="${safe(o.title)}">${safe(o.title)}</div></div>
        <div class="offer-merchant">${v.status==='error'?'Stale listing — not live':state.trust==='review_seller'?'Seller must be checked':'Approved retailer'}<small>${shipping}</small></div>
        <div class="offer-price">${euro(o.price_eur)}<small>Product price</small></div>
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
  $$('.choose-model').forEach(btn=>btn.addEventListener('click',()=>{state.model=btn.dataset.model;state.storage=btn.dataset.storage;state.trust='trusted_retailer';render();$('#offers').scrollIntoView({behavior:'smooth',block:'start'});}));
  $('#share-button').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(location.href);showToast('Dashboard link copied');}
    catch{showToast('Copy this page URL from your browser');}
  });
  $('#whatsapp-link').href='https://wa.me/?text='+encodeURIComponent('iPhone price tracking in Italy — live dashboard: '+location.href);
  Promise.all([
    fetch('./data/latest.json?cache='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Cannot load prices');return r.json();}),
    fetch('./data/history.json?cache='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{})
  ]).then(([latest,history])=>{state.latest=latest;state.history=history;render();})
    .catch(()=>{render();$('#run-status').textContent='Data unavailable';$('#run-status').classList.add('error');});
})();
