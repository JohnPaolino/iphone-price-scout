# iPhone Price Scout — Italy · Operational Guide

## Current deployment
Website: https://johnpaolino.github.io/iphone-price-scout/
Plain HTML price table: https://johnpaolino.github.io/iphone-price-scout/data/prices.html
Actions: https://github.com/JohnPaolino/iphone-price-scout/actions

**Last audited 23 November 2026:** The scanner and GitHub Pages deployment work, but coverage is **degraded**. GitHub's most recent verified scan found 11 fresh numeric prices from retailer pages. Serper responded with `{"message":"Not enough credits"}`; Trovaprezzi and Idealo returned HTTP 403 to GitHub's runner. No Telegram alert recipient is configured. The site's health banner reports these failures and separates fresh and stale prices.

No search system can guarantee checking literally every online shop or buying the cheapest phone the moment its price changes. Search listings can lag merchants, and GitHub's schedule is best-effort.

## What runs now
- `src/reliable_monitor.py` is the production price monitor.
- Runs at approximately **:07, :22, :37 and :52 UTC** each hour via GitHub Actions. GitHub may delay executions.
- Every run checks public comparison pages (when accessible) and previously found direct retailer product pages. A 403 is reported, never bypassed.
- Every hour, a Serper Google Shopping scan is attempted, **if Serper has credits**.
- Optional secondary Google Shopping source: SerpApi (`SERPAPI_API_KEY`).
- Optional Amazon.it new-price source: Keepa API (`KEEPA_API_KEY`). Keepa is necessary for structured Amazon pricing; Amazon product pages often omit readable numeric prices.
- Seven iPhone variants: Pro 256/512GB/1TB, Pro Max 256/512GB/1TB/2TB.
- All prices are visible, including unvetted/marketplace sources, with warning labels; explicit used/refurbished products are excluded.
- The bot displays the source status, number of *fresh* prices, and alert configuration; old observations are retained as **STALE**, not counted as current bargains.
- A JavaScript-free `docs/data/prices.html` is updated each run.

## Step 1 — Restore broad discovery (REQUIRED)
1. Sign in at https://serper.dev/ and open the **billing / credits** screen.
2. Your existing `SERPER_API_KEY` GitHub secret is configured, but its balance is depleted. **Top up the Serper account**; there is no need to replace the secret if the key is still valid.
3. Open https://github.com/JohnPaolino/iphone-price-scout/actions/workflows/monitor.yml and run the workflow manually. Look at the published health banner and `docs/data/latest.json` source statuses.
4. Monitor actual Serper credit consumption. Hourly paid searches are seven Shopping queries per hour (~168 per day before provider-specific multipliers), not the original expensive 30+ query implementation.

**Alternative:** If you prefer SerpApi, obtain an API key at https://serpapi.com/ and create a repository secret named `SERPAPI_API_KEY`. The bot can use it as a second independent Google Shopping data source. It is also paid and its balance/limits need monitoring. Both sources may return overlapping offers and lag actual checkout prices.

## Step 2 — Activate prompt price alerts (REQUIRED)
The bot cannot send a message to a person until you configure an actual destination.

1. Create a Telegram bot through https://t.me/BotFather and privately copy its bot token.
2. Add **GitHub repository secret** `TELEGRAM_BOT_TOKEN` with the bot token.
3. Ask the intended recipient to open the bot and send `/start` in Telegram.
4. Retrieve that recipient's chat ID through Telegram Bot API `getUpdates`, and add repository **Actions variable** `TELEGRAM_CHAT_IDS` with that numeric ID. Multiple chat IDs can be separated with commas.
5. Run the workflow manually and confirm the GitHub log says `alert ready=True`. The site health banner must show **Telegram alerts configured**. Initial discoveries are enabled by default; subsequent lower quotes alert when the best observed price falls at least €2.
6. The monitor keeps `docs/data/alerts.json` with prices **acknowledged by Telegram** so the same offer is not re-alerted every 15 minutes.

Never put tokens/API keys into public repository files, emails, or the website.

## Step 3 — Amazon.it prices (OPTIONAL; STRONGLY RECOMMENDED)
The Keepa API offers price statistics for Amazon.it products, including Amazon's own price and the lowest new marketplace offer. Keepa documents marketplace **NEW** and **AMAZON** price series separately from USED and REFURBISHED. Subscribe at https://keepa.com/ (an API-enabled plan), copy your Keepa API key, and create the GitHub repository secret `KEEPA_API_KEY`. The bot uses known, matching ASINs discovered in earlier Amazon.it product URLs; no price is invented for an ASIN without an eligible new offer.

These optional subscriptions may incur costs. Review provider terms and budgets. Pricing updates reflect data-source refresh times and cannot guarantee instant merchant-price capture.

## How we classify sellers
- **Recognized retailer:** Link domain and retailer name match known chains (Apple, Unieuro, Euronics, Comet, etc.). This does not verify the actual seller.
- **Marketplace / seller to verify:** Google Shopping intermediary links, Amazon/MediaWorld marketplace, or Keepa new offers.
- **Unvetted:** Unknown shops and public comparison-page prices. These may be legitimate but are *not* verified.
- **Excluded:** Listings explicitly used, refurbished, open-box, accessories, or monthly installment-only offers.
- We do **not** guarantee factory seals, VAT/warranty compliance, EU/Italian stock, delivery date, or final checkout totals.

## Troubleshooting
- GitHub Actions failed: inspect the step `Scan Italian prices from independent sources` and the source report under the health banner.
- Health says **Not enough credits**: top up Serper or connect SerpApi. A secret being set does not replenish API credits.
- Trovaprezzi/Idealo HTTP 403: automated access is being refused. The bot will not bypass restrictions; comparison prices require a licensed API or separately approved integration.
- Alerts not configured: configure BOTH `TELEGRAM_BOT_TOKEN` (secret) and `TELEGRAM_CHAT_IDS` (variable); the bot must have an open chat with the recipient.
- All prices stale: the price feed cannot currently observe new quotes; do **not** use the old minimum to assume a bargain exists.
- Need a guaranteed 1-minute reaction? GitHub Actions is not a real-time service. Deploy the same monitor on a continuously running platform with a paid low-latency feed and proper alerting.

## Files
- `src/reliable_monitor.py` — live multi-source monitor, Keepa/SerpApi adapters, alert deduplication, explicit source health.
- `src/monitor.py` — original parsing helpers and legacy tests.
- `config.json` — models, trusted retailer aliases, alert sensitivity.
- `docs/data/latest.json` — recent and stale listing data, plus source health.
- `docs/data/history.json` — price history.
- `docs/data/alerts.json` — acknowledged Telegram-alert baselines.
- `docs/data/prices.html` — static price table.
- `docs/app.js` — dashboard that shows status and fresh vs stale.
- `.github/workflows/monitor.yml` — schedule, tests, scan and deployment.
- `tests/...` — 23+ Python and browser smoke tests.

### Important
This monitoring system helps you react **soon after the next successful observation**, not guarantee the absolute cheapest price across the entire web in real time. You must still verify stock, seller, new-condition status, shipping and final price before buying.
