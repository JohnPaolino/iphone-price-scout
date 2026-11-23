(() => {
  'use strict';
  const state = { model:'all', storage:'all', latest:{variants:{}}, history:{} };
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const euro = (amount) => typeof amount === 'number' ? new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR',maximumFractionDigits:2,minimumFractionDigits:0}).format(amount) : '—';
  const safe = (v) => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const validUrl = (s) => {try { const u=new URL(s);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
  const dateLabel = (date) => date ? new Date(date).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Rome'})+' CET/CEST' : 'Not yet scanned';
  const variant = () => `${state.model==='max'||(state.model==='all'&&state.storage==='2tb')?'pro-max':'pro'}-${state.storage==='all'?'256gb':state.storage}`;
  const current = () => state.latest.variants?.[variant()] || {};
  const vTitle = () => 'iPhone 17 Pro'+(state.model==='max'?' Max':'')+' · '+state.storage.toUpperCase();
  const showToast = (t) => {const el=$('#toast'); el.textContent=t;el.classList.add('visible');setTimeout(()=>el.classList.remove('visible'),2200);};

  function renderHealth(){
    const h=state.latest.health || {};
    const stateName=h.status || (state.latest.checked_at?'legacy':'unknown');
    const stamp=state.latest.checked_at || '';
    const fresh=stamp && (Date.now()-Date.parse(stamp))<55*60*1000;
    const box=$('#health-panel');
    if(!box)return;
    const src=h.sources || {};
    const failed=Object.entries(src).filter(([k,v])=>v.status==='error'||v.status==='partial'||v.status==='unconfigured');
    box.classList.toggle('unhealthy',stateName!=='healthy'||!fresh);
    const heading=!fresh?'SCAN OVERDUE':stateName==='healthy'?'MONITOR ACTIVE':stateName==='degraded'?'PARTIAL COVERAGE':stateName==='outage'?'PRICE SOURCES UNAVAILABLE':'MONITOR STATUS';
    $('#health-title').textContent=heading;
    const hasAlerts=h.alerts_configured===true;
    const failures=failed.map(([k,v])=>k+': '+(v.reason||v.status)).join(' · ');
    $('#health-details').textContent=
      (h.live_prices ?? 'Unknown')+' fresh prices · '+(hasAlerts?'Telegram alerts configured':'ALERTS NOT CONFIGURED')+
      (failures?' · '+failures.slice(0,280):'')+
      ' · Last scan '+dateLabel(stamp);
  }
  function renderSummary(){
    const hasScan=!!state.latest.checked_at;
    const lastMs=Date.parse(state.latest.checked_at || '');
    const isFresh=hasScan && Number.isFinite(lastMs) && (Date.now()-lastMs)<(150*60*1000);
    $('#last-checked').textContent=dateLabel(state.latest.checked_at);
    $('#footer-updated').textContent='Updated: '+dateLabel(state.latest.checked_at);
    const offers=Object.values(state.latest.variants||{}).reduce((n,v)=>n+(v.offers?.filter(o=>typeof o.price_eur==='number'&&!o.stale).length||0),0);
    $('#offer-count').textContent=hasScan?`${offers} quoted prices`:'Awaiting scan';
    const pill=$('#run-status');
    pill.classList.toggle('live',isFresh && !state.latest.error_count);
    pill.classList.toggle('error',hasScan && (!isFresh || !!state.latest.error_count));
    pill.textContent=!hasScan?'Awaiting first scan':!isFresh?'Scan overdue':state.latest.error_count?`Partial scan · ${state.latest.error_count} errors`:'Recent scan';
    for(const [id,prefix] of [['pro-256gb','pro'],['pro-max-256gb','max']]){
      const v=state.latest.variants?.[id]; const best=(v?.offers||[]).filter(o=>typeof o.price_eur==='number'&&!o.stale).sort((a,b)=>a.price_eur-b.price_eur)[0];
      $(`#feature-${prefix}-price`).textContent=best?euro(best.price_eur):'—';
      $(`#feature-${prefix}-seller`).textContent=v?.status==='error'?'Last available result · scan failed':!isFresh&&hasScan?'Last observed price · scan overdue':best?`${best.merchant} · ${best.trust==='trusted_retailer'?'retailer price':'seller needs verification'} · excluding unknown shipping`:hasScan?(v?.offers?.length?'Retailer listings found · check current prices':'No matching retailer pages found'):'Awaiting first scan';
    }
  }

  function renderOffers(){
    $$('[data-model]').forEach(btn=>{
      const selected=btn.dataset.model===state.model;
      btn.classList.toggle('selected',selected);
      btn.setAttribute('aria-pressed',String(selected));
    });
    $$('#storage option').forEach(opt=>{opt.disabled=state.model==='pro'&&opt.value==='2tb';});
    $('#storage').value=state.storage;
    const all=Object.values(state.latest.variants||{}).flatMap(v=>(v.offers||[]).map(o=>({...o,stale:v.status==='error'})));
    const selected=all.filter(o=>
      (state.model==='all'||(state.model==='pro'&&o.model==='Pro')||(state.model==='max'&&o.model==='Pro Max'))&&
      (state.storage==='all'||o.storage?.toLowerCase()===state.storage)
    );
    const priced=selected.filter(o=>typeof o.price_eur==='number'&&Number.isFinite(o.price_eur))
      .sort((a,b)=>Number(!!a.stale)-Number(!!b.stale)||a.price_eur-b.price_eur||String(a.merchant).localeCompare(String(b.merchant)));
    const recognized=priced.filter(o=>o.trust==='trusted_retailer');
    const toCheck=priced.filter(o=>o.trust!=='trusted_retailer');
    const unpriced=selected.filter(o=>o.price_eur==null).sort((a,b)=>String(a.merchant).localeCompare(String(b.merchant)));
    const amazonWithoutQuote=unpriced.filter(o=>o.merchant==='Amazon.it');
    const otherUnpriced=unpriced.filter(o=>o.merchant!=='Amazon.it');
    $('#retailer-count').textContent='('+recognized.length+')';
    $('#unvetted-count').textContent='('+toCheck.length+' priced / '+amazonWithoutQuote.length+' Amazon links)';
    $('#view-summary').textContent=priced.filter(o=>!o.stale).length+' fresh quoted prices across '+
      new Set(priced.filter(o=>!o.stale).map(o=>o.merchant)).size+
      ' seller/source names · '+priced.filter(o=>o.stale).length+' previous quotes retained as STALE'+
      (unpriced.length?' · '+unpriced.length+' links without prices':'');
    $('#view-timestamp').textContent=state.latest.checked_at?'Checked '+dateLabel(state.latest.checked_at):'';
    $('#result-caption').textContent='All quoted prices in EUR; shipping and checkout availability may differ';

    const statusText=(o)=>{
      if(o.stale)return 'STALE · scan failed';
      if(o.trust==='unverified_seller')return 'UNVETTED SELLER · verify identity';
      if(o.trust==='review_seller')return 'MARKETPLACE / SELLER TO VERIFY';
      return o.price_status==='shopping_listing'?'Recognized retailer · Shopping quote':'Recognized retailer · product page';
    };
    const rowMarkup=(rows)=>{
      return rows.map((o,i)=>{
        const link=validUrl(o.link);
        const shipping=o.shipping_eur===0?'Free delivery reported':typeof o.shipping_eur==='number'?'Delivery '+euro(o.shipping_eur):'Delivery cost unconfirmed';
        const source=(o.source_label&&o.source_label!==o.merchant)?o.source_label:'';
        return `<article class="offer-row ${o.trust!=='trusted_retailer'?'review':''}">
          <div class="offer-index ${i===0 && o.price_eur!=null?'best':''}">${i===0&&o.price_eur!=null?'★':i+1}</div>
          <div><div class="offer-name">${safe(o.merchant)}</div>
            <div class="offer-desc">${safe('iPhone 17 '+o.model+' · '+o.storage)} · ${safe(o.title)}</div>
            ${source?'<div class="offer-source">'+safe(source)+'</div>':''}
          </div>
          <div class="offer-merchant">${statusText(o)}<small>${shipping}</small></div>
          <div class="offer-price">${o.price_eur==null?'Check store':euro(o.price_eur)}
            <small>${o.price_eur==null?'Price not provided':o.price_status==='shopping_listing'?'Google Shopping quote':o.price_status==='search_snippet_unverified'?'Search snippet price':'Product-page quote'}</small>
          </div>
          <a class="offer-link" href="${safe(link)}" target="_blank" rel="noopener noreferrer">View listing ↗</a>
        </article>`;
      }).join('');
    };
    $('#offers-list').innerHTML=recognized.length?rowMarkup(recognized):
      '<div class="empty-state">No numeric prices from recognized retailer pages for this selection. Other sellers and store links appear below.</div>';
    $('#unvetted-list').innerHTML=(toCheck.length?rowMarkup(toCheck):'')+
      (amazonWithoutQuote.length?
        '<div class="amazon-links-heading">Amazon.it product pages — price must be checked on Amazon</div>'+
        rowMarkup(amazonWithoutQuote):'')+
      (!toCheck.length&&!amazonWithoutQuote.length?
        '<div class="empty-state">No matching marketplace or unvetted prices in the latest feed.</div>':'');
    $('#unpriced-summary').textContent=otherUnpriced.length+' other store listing'+(otherUnpriced.length===1?'':'s')+' without a readable price';
    $('#unpriced-list').innerHTML=otherUnpriced.length?rowMarkup(otherUnpriced):
      '<div class="empty-state">No additional store links for this selection.</div>';

    const amazon=selected.filter(o=>/^amazon(?:\.it)?(?:$|\s|\s*-)/i.test(o.merchant||o.source_label||''));
    const amazonPriced=amazon.filter(o=>typeof o.price_eur==='number');
    const amazonQuery='Apple iPhone 17 Pro'+(state.model==='max'?' Max':'')+
      (state.storage==='all'?'':' '+state.storage.toUpperCase());
    const amazonLink='https://www.amazon.it/s?k='+encodeURIComponent(amazonQuery);
    $('#amazon-note').innerHTML=amazonPriced.length===0?
      'Amazon.it: no reliably matched numeric price returned for this selection by the current feed. '+
      'This does not mean the product is unavailable. <a href="'+safe(amazonLink)+'" target="_blank" rel="noopener noreferrer">Check Amazon.it directly ↗</a>':
      'Amazon.it offers are shown under Marketplace & sellers to verify. Confirm the actual “Sold by” merchant and product condition before purchasing.';
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
  function render(){renderHealth();renderSummary();renderOffers();renderChart();}
  $$('[data-model]').forEach(btn=>btn.addEventListener('click',()=>{state.model=btn.dataset.model;if(state.model==='pro'&&state.storage==='2tb')state.storage='all';render();}));
  $('#storage').addEventListener('change',e=>{state.storage=e.target.value;render();});
  $$('.choose-model').forEach(btn=>btn.addEventListener('click',()=>{state.model=btn.dataset.model;state.storage=btn.dataset.storage;render();$('#offers').scrollIntoView({behavior:'smooth',block:'start'});}));
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
