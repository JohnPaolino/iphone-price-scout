#!/usr/bin/env python3
"""Resilient multi-source Italian iPhone offer monitor.

Sources are independently monitored. Paid Serper failures do not stop public
comparison-page discovery. Output always reports source health and alert status.
"""
from __future__ import annotations
import hashlib
import html
from html.parser import HTMLParser
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from src import monitor as base

LOG = logging.getLogger("market")
ROOT = Path(__file__).resolve().parent.parent
MONEY = re.compile(r"(?<!\d)(\d{1,2}(?:\.\d{3})+(?:,\d{2})?|\d{3,4},\d{2})\s*€|€\s*(\d{1,2}(?:\.\d{3})+(?:,\d{2})?|\d{3,4},\d{2})", re.I)
TROVA_BASE = "https://www.trovaprezzi.it/cellulari/prezzi-scheda-prodotto/"
INTERNAL_SHOPS = ("Apple", "Unieuro", "Euronics", "Comet", "Trony", "Expert", "MediaWorld", "Amazon.it", "R-Store")
BANNED_SHOP = re.compile(r"refurbed|swappie|back.market|ricondizionat|usato|second.hand|trendevice|certideal|rebuy", re.I)
MISC_LABEL = re.compile(r"prezzo|offert|availability|disponibil|sped|paypal|mastercard|visa|trusted|feedaty|satispay|vedi|acquist|negozio|recension|iPhone|nuovo|promozion|rate|fattura|bonifico|totale|gratuita|gratuito|€", re.I)
UAGENT = "PriceScout/3.0 (+https://github.com/JohnPaolino/iphone-price-scout; personal price monitoring)"

def at_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def is_safe_url(value):
    return base.safe_link(value)

def fetch_html(url, timeout=13):
    if not is_safe_url(url):
        raise ValueError("Unsafe source URL")
    req = urllib.request.Request(url, headers={"User-Agent":UAGENT,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200 or "html" not in resp.headers.get("content-type", "").lower():
                raise RuntimeError("Unexpected public page response")
            final = resp.geturl()
            if not is_safe_url(final):
                raise ValueError("Unsafe public page redirect")
            data = resp.read(3_000_001)
            if len(data) > 3_000_000:
                raise RuntimeError("Public page is larger than configured limit")
            return data.decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP " + str(e.code)) from e

class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens=[]
        self.skip=0
        self.anchors=[]
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","template","svg"):
            self.skip+=1
        if tag=="a":
            self.anchors.append(dict(attrs).get("href",""))
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript","template","svg"):
            self.skip=max(self.skip-1,0)
        if tag=="a" and self.anchors:
            self.anchors.pop()
    def handle_data(self, value):
        if not self.skip and (value:=value.strip()):
            self.tokens.append((value, self.anchors[-1] if self.anchors else ""))

def best_offer_price(segment):
    # Ignore extracted decimal ratings (4,9 etc): prices must be EUR and > €650.
    prices=[]
    for m in MONEY.finditer(segment):
        amount=base.parse_eur(m.group(1) or m.group(2))
        if amount and 650 <= amount <= 4500:
            prices.append((amount,m.start()))
    return prices

def trobaprezzi_url(model,gb):
    slug=("apple_iphone_17_pro_max_" if model=="Pro Max" else "apple_iphone_17_pro_")+base.storage_label(gb).lower()
    return TROVA_BASE+slug+"-v"

def parse_comparison_html(raw, page_url, model, gb, scanned, source="Trovaprezzi"):
    """Extract individual indexed offer titles/prices from a public comparison page.

    Parsed values are indicative: seller identity and checkout price are not
    independently verified. No listing is marked as 'trusted retailer'.
    """
    vis=Visible()
    vis.feed(raw)
    tokens=vis.tokens
    offers=[]
    # Match title tokens (may be broken into multiple tokens by HTML markup).
    # Candidate pages without explicit storage are never treated as an exact SKU.
    for i,(label,href) in enumerate(tokens):
        title=label
        if not base.title_matches(title,model,gb):
            continue
        if base.BAD_CONDITION.search(title) or base.BAD_OFFER.search(title):
            continue
        context=tokens[i+1:i+42]
        if not context:
            continue
        # Stop at the next (different) iPhone listing, preventing price
        # bleed-through between unrelated sizes.
        cut=len(context)
        for k,(part,_) in enumerate(context):
            if k>0 and re.search(r"\biPhone\s+17\b",part,re.I):
                cut=k;break
        context=context[:cut]
        joined=" ".join(t for t,_ in context)
        found=best_offer_price(joined)
        if not found:
            continue
        # Use the first explicit product price, not the shipping-inclusive
        # total or a different offer's price.
        price=found[0][0]
        merchant=""
        for part,_ in context[:14]:
            clean=part.strip(" -\u00a0")
            if 3<=len(clean)<=55 and not MISC_LABEL.search(clean) and not re.fullmatch(r"[\d\W]+",clean):
                merchant=clean
                break
        if not merchant:
            merchant=source+" · merchant unconfirmed"
        if BANNED_SHOP.search(merchant):
            continue
        # Link to the comparison item or the comparison page; never invent
        # a merchant-specific checkout destination.
        href=urllib.parse.urljoin(page_url,href) if href else page_url
        if not is_safe_url(href) or not href.startswith("https://"):
            href=page_url
        offers.append({
            "variant_id":base.variant_id(model,gb),"model":model,"storage":base.storage_label(gb),
            "title":title[:240],"merchant":merchant[:80],"source_label":source+" public comparison",
            "price_eur":price,"shipping_eur":None,"total_eur":None,"shipping_known":False,
            "link":href,"trust":"unverified_seller","link_quality":"comparison_page",
            "price_status":"comparison_indicative","condition":"not_declared_refurbished",
            "observed_at":scanned,"provider":source.lower(),
        })
    # If individual offers were not parsable, expose a minimum as an
    # unassigned aggregate instead of silently showing zero.
    if not offers:
        flat=" ".join(t for t,_ in tokens[:5000])
        head=flat[:2500]
        if re.search(r"iPhone\s*17\s*Pro",head,re.I):
            match=re.search(r"(?:a\s+partire\s+da|da|prezzo\s+pi[uù]\s+basso)\s*€?\s*([0-9][0-9.,]{4,})\s*€?",head,re.I)
            if match:
                value=base.parse_eur(match.group(1))
                if value and 650<=value<=4500:
                    offers.append({
                        "variant_id":base.variant_id(model,gb),"model":model,"storage":base.storage_label(gb),
                        "title":f"Indexed starting price for iPhone 17 {model} {base.storage_label(gb)}",
                        "merchant":source+" · seller unspecified","source_label":source+" minimum",
                        "price_eur":value,"shipping_eur":None,"total_eur":None,"shipping_known":False,
                        "link":page_url,"trust":"unverified_seller","link_quality":"comparison_page",
                        "price_status":"comparison_indicative","condition":"not_declared_refurbished",
                        "observed_at":scanned,"provider":source.lower(),
                    })
    return offers[:80]

def serp_request(endpoint, query, key):
    data=json.dumps({"q":query,"gl":"it","hl":"it","num":30}).encode()
    req=urllib.request.Request("https://google.serper.dev/"+endpoint,
        data=data, headers={"X-API-KEY":key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=16) as resp:
            response=json.load(resp)
            return response.get("shopping" if endpoint=="shopping" else "organic",[])
    except urllib.error.HTTPError as e:
        detail=e.read(700).decode("utf-8","replace")
        detail=detail.replace(key,"[redacted]") if key else detail
        # Surface the reason in job logs and health, never credentials.
        raise RuntimeError("Serper HTTP "+str(e.code)+": "+detail[:220]) from e

def offer_key(o):
    normalized_link=(o.get("link") or "").split("?")[0]
    return (o.get("variant_id"),o.get("merchant","").casefold(),normalized_link,
            o.get("price_eur"))

def unique_offers(items):
    seen={}
    for x in items:
        if x.get("price_eur") is not None and not 650<=x["price_eur"]<=4500:
            continue
        key=offer_key(x)
        # Prefer direct store links over Google intermediaries on duplicates.
        if key not in seen or x.get("link_quality")=="direct":
            seen[key]=x
    return sorted(seen.values(),key=lambda o:(o.get("price_eur") is None,
                  o.get("price_eur") if o.get("price_eur") is not None else 999999,
                  o.get("merchant","")))

def telegram_send_safe(token, chat_id, msg):
    if not token or not chat_id:
        return False
    base.telegram_send(token,chat_id,msg)
    return True

def calculate_alerts(current,prev,history,config):
    """Alerts on observed new best or a threshold, never on stale observations.

    Only numeric current quotes are eligible. No repeated alerts for identical
    previous best. Comparison prices are explicitly labelled indicative.
    """
    result=[]
    first=bool(config.get("alert_on_first_discovery",True))
    drop=float(config.get("alert_min_drop_eur",5))
    for vid,v in current.items():
        priced=[o for o in v.get("offers",[]) if o.get("price_eur") is not None and not o.get("stale")]
        if not priced:
            continue
        best=min(priced,key=lambda x:x["price_eur"])
        old=prev.get(vid,{})
        old_prices=[x["price_eur"] for x in old.get("offers",[])
                    if x.get("price_eur") is not None and not x.get("stale")]
        last_min=min(old_prices) if old_prices else None
        threshold_txt=os.environ.get("ALERT_"+vid.upper().replace("-","_"),"").strip()
        threshold=base.parse_eur(threshold_txt) if threshold_txt else None
        new_low= last_min is not None and best["price_eur"]<=last_min-drop
        first_seen=last_min is None and first
        crossed=threshold is not None and best["price_eur"]<=threshold and (
                 last_min is None or last_min>threshold)
        if new_low or first_seen or crossed:
            status="UNVERIFIED / CHECK SELLER" if best["trust"]!="trusted_retailer" else "recognized retailer (seller not audited)"
            msg=(f"📉 Price Scout: iPhone 17 {v['model']} {v['storage']}\n"
                 f"€{best['price_eur']:,.2f} · {best['merchant']}\n"
                 f"{status} · quoted price, check stock/shipping\n{best['link']}")
            result.append({"variant_id":vid,"merchant":best["merchant"],"price_eur":best["price_eur"],"message":msg,
                           "reason":"new_low" if new_low else "threshold" if crossed else "first_discovery"})
    return result

def run():
    config=base.load_json(ROOT/"config.json",{})
    out=ROOT/"docs"/"data"
    prev_doc=base.load_json(out/"latest.json",{})
    old=prev_doc.get("variants",{})
    history=base.load_json(out/"history.json",{})
    scan=at_now()
    key=os.environ.get("SERPER_API_KEY","")
    # Our default cadence is comparison-first. Run the paid feed only on the
    # hourly cron or manually, preserving credits.
    paid=os.environ.get("RUN_PAID_SEARCH","false").lower()=="true"
    sources={}
    new={}
    price_count=0
    any_fresh=False
    paid_available=bool(key and paid)
    serper_outage=None
    for model,storages in config["storage_gb"].items():
        for gb in storages:
            vid=base.variant_id(model,gb)
            offers=[]
            page=trobaprezzi_url(model,gb)
            try:
                raw=fetch_html(page)
                extracted=parse_comparison_html(raw,page,model,gb,scan)
                offers.extend(extracted)
                any_fresh=any_fresh or bool(extracted)
                sources.setdefault("trovaprezzi",{"status":"ok","variants":0,"offers":0})
                sources["trovaprezzi"]["variants"]+=1
                sources["trovaprezzi"]["offers"]+=len(extracted)
            except Exception as e:
                s=sources.setdefault("trovaprezzi",{"status":"partial","variants":0,"offers":0,"errors":[]})
                s["status"]="partial";s.setdefault("errors",[]).append(vid+": "+str(e)[:120])
            # Last known direct store URLs (such as Unieuro) are useful even
            # during paid-provider outage. Recheck a limited set; omit broken
            # pages without claiming their old price is current.
            direct_seen=set()
            for oldoffer in old.get(vid,{}).get("offers",[]):
                if oldoffer.get("link_quality")!="direct":
                    continue
                link=oldoffer.get("link","")
                domain=(urllib.parse.urlsplit(link).hostname or "").lower()
                if domain not in ("www.unieuro.it","unieuro.it","www.euronics.it","euronics.it"):
                    continue
                canonical=urllib.parse.urlunsplit((*urllib.parse.urlsplit(link)[:3],"",""))
                if canonical in direct_seen:continue
                direct_seen.add(canonical)
                try:
                    shop=oldoffer["merchant"]
                    amount=base.fetch_retailer_price(link,shop,model,gb,config)
                    if amount is not None:
                        fresh=dict(oldoffer,price_eur=amount,price_status="retailer_page_price",
                                   observed_at=scan,provider="retailer_page",stale=False)
                        offers.append(fresh);any_fresh=True
                except Exception as e:
                    LOG.warning("Direct price %s: %s",vid,str(e)[:120])
                if len(direct_seen)>=2:break
            # Serper is optional. A quota error aborts the remaining paid
            # requests, instead of multiplying 7 errors.
            if paid_available:
                try:
                    rows=serp_request("shopping",f"Apple iPhone 17 {model} {base.storage_label(gb)}",key)
                    normalized=[o for x in rows if isinstance(x,dict)
                                if (o:=base.normalize_item(x,model,gb,config))]
                    for x in normalized:
                        x["provider"]="serper_shopping";x["observed_at"]=scan;x["stale"]=False
                    offers.extend(normalized)
                    any_fresh=any_fresh or bool(normalized)
                    state=sources.setdefault("serper_shopping",{"status":"ok","variants":0,"offers":0})
                    state["variants"]+=1;state["offers"]+=len(normalized)
                except Exception as e:
                    serper_outage=str(e)
                    paid_available=False
                    sources["serper_shopping"]={"status":"error","reason":serper_outage}
            # Preserve prior listings, visibly stale and never eligible for
            # alerts, when current discovery has gaps.
            current_keys={(o.get("merchant"),o.get("link","").split("?")[0]) for o in offers}
            for x in old.get(vid,{}).get("offers",[]):
                lk=(x.get("merchant"),x.get("link","").split("?")[0])
                if lk not in current_keys:
                    stale=dict(x,stale=True,price_status="historical_price",
                               observed_at=x.get("observed_at") or old.get(vid,{}).get("checked_at"))
                    offers.append(stale)
            offers=unique_offers(offers)
            priced=[o for o in offers if o.get("price_eur") is not None and not o.get("stale")]
            price_count+=len(priced)
            new[vid]={"model":model,"storage":base.storage_label(gb),
                      "status":"ok" if priced else "stale","checked_at":scan if priced else old.get(vid,{}).get("checked_at"),
                      "offers":offers,
                      "results_checked":len(offers),
                      "best_trusted":next((x for x in priced if x.get("trust")=="trusted_retailer"),None),
                      "best_review":next((x for x in priced if x.get("trust")!="trusted_retailer"),None)}
    if not paid:
        sources["serper_shopping"]={"status":"skipped","reason":"Hourly paid search disabled on interim check"}
    elif not key:
        sources["serper_shopping"]={"status":"unconfigured","reason":"No SERPER_API_KEY secret"}
    health=("healthy" if price_count and all(x.get("status") in ("ok","skipped") for x in sources.values())
            else "degraded" if price_count else "outage")
    token=os.environ.get("TELEGRAM_BOT_TOKEN","")
    chatids=[x.strip() for x in os.environ.get("TELEGRAM_CHAT_IDS","").split(",") if x.strip()]
    ready=bool(token and chatids)
    alerts=calculate_alerts(new,old,history,config)
    delivered=0
    errors=[]
    # Don't claim notification success from telegram_send() which deliberately
    # swallows errors; direct HTTP verification is in follow-up improvements.
    for a in alerts:
        if ready:
            for cid in chatids:
                try:
                    telegram_send_safe(token,cid,a["message"]);delivered+=1
                except Exception as e:
                    errors.append("Telegram: "+type(e).__name__)
    for vid,v in new.items():
        best=next((x for x in v["offers"] if x.get("price_eur") is not None and not x.get("stale")),None)
        if best:
            history.setdefault(vid,[]).append({"at":scan,"merchant":best["merchant"],"price_eur":best["price_eur"]})
            history[vid]=history[vid][-config["max_history_points_per_variant"]:]
    doc={"checked_at":scan,"market":"Italy","currency":"EUR",
         "source":"Independent public comparisons + retailer pages + optional Serper",
         "success_count":sum(v["status"]=="ok" for v in new.values()),
         "error_count":sum(v["status"]!="ok" for v in new.values()),
         "errors":errors,"variants":new,
         "health":{"status":health,"live_prices":price_count,"sources":sources,"alerts_configured":ready,
                   "alerts_found":len(alerts),"alerts_sent":delivered,
                   "notes":"Stale prices and comparison quotes are not confirmed checkout prices."},
         "methodology":"All exact-model prices shown; comparison/marketplace prices require seller checks, used/refurb excluded."}
    out.mkdir(parents=True,exist_ok=True)
    base.save_json(out/"latest.json",doc)
    base.save_json(out/"history.json",history)
    base.save_plain_price_table(doc,out/"prices.html")
    LOG.info("HEALTH %s; fresh prices=%s; alert ready=%s; alerts=%s; sent=%s",
             health,price_count,ready,len(alerts),delivered)
    LOG.info("SOURCES %s",json.dumps(sources)[:2500])
    return doc

def main():
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    run()

if __name__=="__main__":
    main()
