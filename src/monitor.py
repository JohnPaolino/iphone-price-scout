#!/usr/bin/env python3
"""Hourly Italian iPhone price discovery using Serper Google Shopping.

* No direct store scraping, avoids robots/captcha issues.
* Trustlist, exact model and capacity, excludes explicitly used/refurbished.
* Marketplace-type retailers are flagged as 'seller verification required'.
* Price is product price; shipping added only when clearly stated.
* Telegram alerts only on newly observed all-time lows (or thresholds).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("price-scout")
BAD_CONDITION = re.compile(
    r"\b(?:refurbished|renewed|ricondizionat\w*|rigenerat\w*|usato|usata|used|"
    r"second.hand|pre.owned|reconditioned|grado\s+[abc]|grade\s+[abc]|"
    r"open.box|scatola\s+aperta|ricondizionato|esposizione|ex.demo|"
    r"da\s+esposizione|solo\s+scatola|per\s+pezzi|come\s+nuovo|open\s*box|b.stock|repackaged|ex\s*display|outlet|demo)\b", re.I
)
BAD_OFFER = re.compile(
    r"\b(?:cover|custodia|pellicola|vetro\s+temperato|protezione|"
    r"accessori|case\s+for|ricambio|sostituzione\s+schermo|"
    r"acconto|anticipo|rata\s+mensile|rate\s+mensili|mese|"
    r"abbonamento|contratto|con\s+permuta|trade.in|no\s+iphone)\b", re.I
)
MAX_WORDS = re.compile(r"\b(?:pro\s*max|promax)\b", re.I)
MODEL_RE = re.compile(r"\biphone\s*17\s*pro\b", re.I)


def storage_label(gb: int) -> str:
    return f"{gb // 1024}TB" if gb >= 1024 else f"{gb}GB"


def variant_id(model: str, gb: int) -> str:
    return ("pro-max" if model == "Pro Max" else "pro") + "-" + storage_label(gb).lower()


def parse_eur(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if value > 0 else None
    text = str(value).replace("\u00a0", "").replace(" ", "")
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    s = match.group(0).rstrip(".,")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        s = s.replace(",", ".") if len(parts[-1]) <= 2 else s.replace(",", "")
    elif "." in s and len(s.split(".")[-1]) == 3:
        s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def shipping_eur(item: dict) -> float | None:
    value = item.get("delivery", "")
    if isinstance(value, dict):
        value = " ".join(map(str, value.values()))
    text = str(value or "").lower()
    if re.search(r"(?:spedizione|consegna|shipping|delivery).{0,30}(?:gratis|gratuita|free)|(?:gratis|gratuita|free).{0,30}(?:spedizione|consegna|shipping|delivery)", text):
        return 0.0
    # Do not accidentally interpret "delivery in 2 days" as a €2 charge.
    if not re.search(r"(?:€|\beur\b)", text, re.I):
        return None
    m = re.search(r"(?:spedizione|consegna|shipping|delivery).{0,40}?(?:€\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:€|eur))", text)
    if not m:
        m = re.search(r"(?:€\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:€|eur)).{0,25}(?:spedizione|consegna|shipping|delivery)", text)
    return parse_eur(m.group(1) or m.group(2)) if m else None


def title_matches(title: str, model: str, gb: int) -> bool:
    if not MODEL_RE.search(title):
        return False
    if bool(MAX_WORDS.search(title)) != (model == "Pro Max"):
        return False
    storage = storage_label(gb)
    regex = rf"(?<!\d){gb}\s*(?:gb|g)(?!\w)" if gb < 1024 else rf"(?<!\d){gb // 1024}\s*(?:tb|t)(?!\w)"
    # Google Shopping sometimes writes 1024GB / 2048GB instead of 1TB/2TB.
    return bool(re.search(regex, title, re.I) or (gb >= 1024 and re.search(rf"(?<!\d){gb}\s*gb\b", title, re.I)))


def canonical_merchant(source: str, config: dict) -> str | None:
    cleaned = re.sub(r"[^a-z0-9]+", "", source.casefold())
    for name, aliases in config["trusted_merchants"].items():
        for alias in aliases:
            ac = re.sub(r"[^a-z0-9]+", "", alias.casefold())
            if cleaned == ac:
                return name
    return None


# Merchant names alone are not sufficient: a listing can contain an unsafe link.
# Keep the allowlist narrow and only link to exact retailer domains or their subdomains.
RETAILER_HOSTS = {
    "Apple": ("apple.com",),
    "Unieuro": ("unieuro.it",),
    "Euronics": ("euronics.it",),
    "Comet": ("comet.it",),
    "Trony": ("trony.it",),
    "Expert": ("expert.it",),
    "MediaWorld": ("mediaworld.it",),
    "Amazon.it": ("amazon.it",),
    "R-Store": ("rstore.it",),
}


def link_quality(raw: str, merchant: str) -> str | None:
    """Return direct, google_shopping, or None (unapproved URL)."""
    link = safe_link(raw)
    if not link or merchant not in RETAILER_HOSTS:
        return None
    u = urllib.parse.urlsplit(link)
    host = (u.hostname or "").lower().rstrip(".")
    try:
        if u.port not in (None, 443):
            return None
    except ValueError:
        return None
    if any(host == domain or host.endswith("." + domain) for domain in RETAILER_HOSTS[merchant]):
        return "direct"
    # Google Shopping is a recognized intermediary, but not verified as the seller.
    if host in ("google.com", "www.google.com", "shopping.google.com"):
        if u.path == "/shopping" or u.path.startswith("/shopping/"):
            return "google_shopping"
        # Serper Shopping frequently links to the Google shopping overlay,
        # not the merchant. Display these only in the seller-review category.
        if u.path == "/search" and "oshop" in urllib.parse.parse_qs(u.query).get("ibp", []):
            return "google_shopping"
    return None


def safe_link(raw: str) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return None
    return raw


def normalize_item(item: dict, model: str, gb: int, config: dict) -> dict | None:
    title = str(item.get("title") or "").strip()
    if not title_matches(title, model, gb):
        return None
    secondhand = item.get("secondHandCondition", item.get("second_hand_condition"))
    if secondhand is True or (isinstance(secondhand, dict) and secondhand):
        return None
    condition_blob = " ".join(map(str, [title, item.get("snippet", ""), item.get("condition", ""), secondhand or "", item.get("tag", "")]))
    if BAD_CONDITION.search(condition_blob) or BAD_OFFER.search(condition_blob):
        return None
    source = str(item.get("source") or "").strip()
    merchant = canonical_merchant(source, config)
    if not merchant:
        return None
    price = parse_eur(item.get("price") or item.get("extractedPrice") or item.get("extracted_price"))
    if not price or not config["min_price_eur"] <= price <= config["max_price_eur"]:
        return None
    link = safe_link(item.get("link") or item.get("productLink") or item.get("product_link") or "")
    quality = link_quality(link, merchant)
    if not quality:
        return None
    shipping = shipping_eur(item)
    review = merchant in config["marketplace_review_merchants"] or quality != "direct"
    return {
        "variant_id": variant_id(model, gb), "model": model, "storage": storage_label(gb),
        "title": title[:240], "merchant": merchant, "price_eur": price,
        "shipping_eur": shipping,
        "total_eur": round(price + shipping, 2) if shipping is not None else None,
        "link": link, "trust": "review_seller" if review else "trusted_retailer",
        "link_quality": quality,
        "condition": "not_declared_refurbished",  # Search results cannot prove sealed/new stock.
        "shipping_known": shipping is not None,
    }


def get_shopping(query: str, key: str, retry=2) -> list[dict]:
    req = urllib.request.Request(
        "https://google.serper.dev/shopping",
        data=json.dumps({"q": query, "gl": "it", "hl": "it", "num": 40}).encode(),
        headers={"X-API-KEY": key, "Content-Type": "application/json", "User-Agent": "iphone-price-scout/1.0"},
        method="POST",
    )
    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(req, timeout=28) as response:
                data = json.load(response)
            if not isinstance(data.get("shopping"), list):
                raise RuntimeError("No shopping array in Serper response; check credits/response format")
            return data["shopping"]
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt == retry:
                raise RuntimeError(f"Shopping API failed: {exc}") from exc
            time.sleep(2 ** attempt)
    return []


def get_organic(query: str, key: str, retry: int = 2) -> list[dict]:
    """Find direct product pages at approved Italian stores via Serper Search."""
    request = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": query, "gl": "it", "hl": "it", "num": 20}).encode(),
        headers={"X-API-KEY": key, "Content-Type": "application/json",
                 "User-Agent": "iphone-price-scout/1.1"},
        method="POST",
    )
    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(request, timeout=28) as response:
                result = json.load(response)
            if not isinstance(result.get("organic"), list):
                raise RuntimeError("No organic results returned")
            return result["organic"]
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt == retry:
                raise RuntimeError(f"Organic search failed: {exc}") from exc
            time.sleep(2 ** attempt)
    return []


def merchant_from_url(raw_link: str, config: dict) -> str | None:
    link = safe_link(raw_link)
    if not link:
        return None
    host = (urllib.parse.urlsplit(link).hostname or "").lower().rstrip(".")
    for merchant in config["trusted_merchants"]:
        if any(host == domain or host.endswith("." + domain)
               for domain in RETAILER_HOSTS.get(merchant, ())):
            return merchant
    return None


def organic_price(item: dict, config: dict) -> float | None:
    """Only accept a clearly labelled price; never infer it from instalments or MSRP."""
    value = item.get("price")
    if value is not None:
        amount = parse_eur(value)
        if amount is not None and config["min_price_eur"] <= amount <= config["max_price_eur"]:
            return amount
    snippet = str(item.get("snippet") or "")
    patterns = (
        r"(?:\\bora|prezzo\\s+(?:attuale|online|scontato)|nostro\\s+prezzo)\\s*[:\\-]?\\s*€?\\s*(\\d[\\d.,]*)(?:\\s*€)?",
        r"€\\s*(\\d{1,2}(?:[.]\\d{3})+(?:[,]\\d{2})?)",
    )
    for pattern in patterns:
        match = re.search(pattern, snippet, re.I)
        if match:
            preceding = snippet[max(0, match.start() - 34):match.start()].lower()
            if re.search(r"prezzo\\s+(?:precedente|consigliato|originale)|anzich[eé]|risparmia", preceding):
                continue
            amount = parse_eur(match.group(1))
            if amount is not None and config["min_price_eur"] <= amount <= config["max_price_eur"]:
                return amount
    return None


def normalize_organic(item: dict, model: str, gb: int, config: dict) -> dict | None:
    """Direct merchant result: never treat Google snippets as checkout-confirmed."""
    title = str(item.get("title") or "").split(" | ")[0].strip()
    if not title_matches(title, model, gb):
        return None
    link = str(item.get("link") or "")
    merchant = merchant_from_url(link, config)
    if not merchant or link_quality(link, merchant) != "direct":
        return None
    path = urllib.parse.urlsplit(link).path.lower()
    if any(chunk in path for chunk in ("/search", "/ricondizionati", "/outlet", "/usato", "/accessori/")):
        return None
    condition_blob = " ".join((title, str(item.get("snippet") or "")))
    # Product pages can mention refurbished alternatives in snippets; exclude
    # explicit used/refurbished *products* on the title or in URL, not every
    # mention of a separate refurbished alternative on a normal product page.
    if BAD_CONDITION.search(title + " " + path) or BAD_OFFER.search(title):
        return None
    price = organic_price(item, config)
    return {
        "variant_id": variant_id(model, gb), "model": model,
        "storage": storage_label(gb), "title": title[:240],
        "merchant": merchant, "price_eur": price,
        "shipping_eur": None, "total_eur": None, "shipping_known": False,
        "link": link,
        # Search snippets may be outdated; do not treat their amounts as
        # verified prices or trigger low-price alerts from them.
        "trust": "review_seller" if price is not None or
                 merchant in config["marketplace_review_merchants"] else "trusted_retailer",
        "link_quality": "direct",
        "price_status": "search_snippet_unverified" if price is not None else "check_on_store",
        "condition": "not_declared_refurbished",
    }


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def telegram_send(token: str, chat_id: str, message: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.load(response)
            if not result.get("ok"):
                LOG.warning("Telegram API returned error: %s", str(result)[:120])
    except urllib.error.URLError as exc:
        LOG.warning("Telegram notification failed: %s", exc)


def make_alerts(latest: dict, previous: dict, history: dict, config: dict, dashboard_url: str) -> list[str]:
    alerts = []
    for key, current in latest.items():
        # Never send an alert for a stale result carried forward after an API failure.
        if current.get("status") != "ok":
            continue
        trusted = [x for x in current["offers"] if x["trust"] == "trusted_retailer"]
        if not trusted:
            continue
        best = trusted[0]
        old_best = previous.get(key, {}).get("best_trusted")
        prior_prices = [p["price_eur"] for p in history.get(key, []) if p.get("price_eur") is not None]
        lifetime_min = min(prior_prices) if prior_prices else None
        first = old_best is None and lifetime_min is None
        new_low = not first and (lifetime_min is None or best["price_eur"] <= lifetime_min - config["alert_min_drop_eur"])
        threshold = os.environ.get("ALERT_" + key.upper().replace("-", "_"), "").strip()
        crossing = bool(threshold and parse_eur(threshold) is not None and best["price_eur"] <= parse_eur(threshold)
                        and (not old_best or old_best["price_eur"] > parse_eur(threshold)))
        if not (new_low or crossing or (first and config["alert_on_first_discovery"])):
            continue
        alerts.append(
            f"📉 iPhone 17 {current['model']} {current['storage']} — €{best['price_eur']:.2f}\n"
            f"Store: {best['merchant']}\n"
            f"Price excludes unverified delivery charges.\n"
            f"{best['link']}" + (f"\nDashboard: {dashboard_url}" if dashboard_url else "")
        )
    return alerts


def run(config_path: Path, out_dir: Path, *, api_key: str, dry_run: bool, fixtures: Path | None) -> None:
    config = load_json(config_path, None)
    if config is None:
        raise RuntimeError("Could not load config.json")
    if not api_key and fixtures is None:
        raise RuntimeError("Missing SERPER_API_KEY. Set the GitHub Actions repository secret.")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    previous_doc = load_json(out_dir / "latest.json", {})
    previous = previous_doc.get("variants", {})
    history = load_json(out_dir / "history.json", {})
    new_variants = {}
    errors = []
    raw_fixtures = load_json(fixtures, {}) if fixtures else {}
    for model, storages in config["storage_gb"].items():
        for gb in storages:
            vid = variant_id(model, gb)
            # Keep discovery broad; enforce condition/model/trust AFTER fetching
            # results. Negative keywords drastically reduce Shopping coverage.
            query = f'Apple iPhone 17 {model} {storage_label(gb)}'
            LOG.info("Checking %s", vid)
            try:
                rows = raw_fixtures.get(vid, []) if fixtures else get_shopping(query, api_key)
                if not isinstance(rows, list):
                    raise ValueError("Shopping result is not a list")
                offers = [o for x in rows if (o := normalize_item(x, model, gb, config))]
                # Shopping generally provides Google redirect links and often
                # omits storage from titles. Complement it with direct URLs
                # from major retailers' indexed product pages.
                organic_query = (
                    f'"iPhone 17 {model}" {storage_label(gb)} '
                    '(site:unieuro.it OR site:mediaworld.it OR site:euronics.it '
                    'OR site:comet.it OR site:trony.it OR site:expert.it '
                    'OR site:rstore.it OR site:apple.com)'
                )
                try:
                    organic_rows = [] if fixtures else get_organic(organic_query, api_key)
                    offers.extend(o for x in organic_rows
                                  if (o := normalize_organic(x, model, gb, config)))
                except Exception as organic_exc:
                    LOG.warning("Direct-retailer discovery unavailable for %s: %s", vid, organic_exc)
                if rows and not offers:
                    # Diagnostic only; do not log API credentials, full links, or pricing.
                    samples = [
                        {"source": str(x.get("source", ""))[:40],
                         "title": str(x.get("title", ""))[:100],
                         "link_host": urllib.parse.urlsplit(str(x.get("link") or "")).hostname}
                        for x in rows[:4] if isinstance(x, dict)
                    ]
                    LOG.warning("No accepted offers for %s; sample results=%s", vid, json.dumps(samples, ensure_ascii=False))
                unique = {}
                for offer in offers:
                    k = (offer["merchant"], offer["price_eur"], offer["link"])
                    unique[k] = offer
                offers = sorted(unique.values(), key=lambda o: (o["price_eur"] is None, o["price_eur"] or 0, o["merchant"]))
                trusted = [x for x in offers if x["trust"] == "trusted_retailer"]
                review = [x for x in offers if x["trust"] == "review_seller"]
                new_variants[vid] = {
                    "model": model, "storage": storage_label(gb), "status": "ok", "offers": offers,
                    "best_trusted": next((o for o in trusted if o["price_eur"] is not None), None),
                    "best_review": next((o for o in review if o["price_eur"] is not None), None),
                    "checked_at": now, "results_checked": len(rows),
                }
            except Exception as exc:
                LOG.error("Failed %s: %s", vid, exc)
                errors.append(f"{vid}: {exc}")
                # NEVER show stale prices as fresh. Keep old offers with explicit stale status.
                old = previous.get(vid, {})
                new_variants[vid] = {"model": model, "storage": storage_label(gb), "status": "error",
                                     "offers": old.get("offers", []), "best_trusted": old.get("best_trusted"),
                                     "best_review": old.get("best_review"), "checked_at": old.get("checked_at"),
                                     "results_checked": 0}

    good = [v for v in new_variants.values() if v["status"] == "ok"]
    if not good:
        raise RuntimeError("Every shopping query failed; data has NOT been overwritten")
    if not any(v["results_checked"] > 0 for v in good):
        raise RuntimeError("Every Shopping query returned zero results; refusing to erase earlier prices")
    dashboard_url = os.getenv("DASHBOARD_URL", "").strip()
    alert_messages = make_alerts(new_variants, previous, history, config, dashboard_url)
    for vid, variant in new_variants.items():
        if variant["status"] != "ok":
            continue
        best = variant["best_trusted"]
        history.setdefault(vid, []).append({
            "at": now, "price_eur": best["price_eur"] if best else None,
            "merchant": best["merchant"] if best else None,
        })
        history[vid] = history[vid][-config["max_history_points_per_variant"]:]
    latest = {
        "checked_at": now,
        "market": "Italy", "currency": "EUR", "source": "Google Shopping / Serper",
        "success_count": len(good), "error_count": len(errors), "errors": errors,
        "methodology": "Approved merchants only; review-seller offers not counted as verified. Prices may exclude delivery costs; verify new/sealed status and seller at checkout.",
        "variants": new_variants,
    }
    if not dry_run:
        save_json(out_dir / "latest.json", latest)
        save_json(out_dir / "history.json", history)
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_ids = [x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()]
        for chat in chat_ids:
            for message in alert_messages:
                telegram_send(token, chat, message)
    LOG.info("Checked %s variants, %s errors, %s alerts. Dry run=%s", len(good), len(errors), len(alert_messages), dry_run)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "data")
    parser.add_argument("--fixtures", type=Path, help="Test against offline fixture JSON; not live")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        run(args.config, args.out, api_key=os.getenv("SERPER_API_KEY", ""), dry_run=args.dry_run, fixtures=args.fixtures)
    except Exception as exc:
        LOG.error("Monitor failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
