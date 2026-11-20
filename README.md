# Price Scout — new iPhone 17 Pro / Pro Max in Italy

A working, deployable **hourly** price-monitoring application, with a shareable GitHub Pages dashboard and optional Telegram price-drop alerts. Backend uses the **Serper Google Shopping API** rather than fragile store scraping. This project uses only Python's standard library and a static HTML/CSS/JS front-end.

## What it monitors

- iPhone 17 **Pro**: 256GB, 512GB, 1TB.
- iPhone 17 **Pro Max**: 256GB, 512GB, 1TB, 2TB.
- Search region and language: Italy / Italian; prices in EUR.
- Only exact model+storage matches; filters used/refurbished/renewed listings, accessories and contracts.
- Trusted-retailer list: Apple, Unieuro, Euronics, Comet, Trony, Expert, plus **seller-review only** listings from Amazon.it and MediaWorld.
- Prices in the dashboard are product prices. Shipping is listed separately when detected; checkout may differ.
- Important: an offer appearing on Google Shopping is **not** proof of factory-sealed condition, stock availability, Italian warranty, or that the merchant is the actual seller. Check the listing before buying. Marketplaces are deliberately never included in the trusted best-price figure.

## Quick deployment (approx. 6 steps)

1. Create a GitHub repository called `iphone-price-scout` with the **main** default branch. A public repository is simplest for a shareable public site.
2. Upload **all contents** of this package into that repository (including the hidden `.github/workflows/monitor.yml` folder). Do not upload the ZIP as one file.
3. Sign up at [Serper.dev](https://serper.dev/), obtain a Google Shopping API key. In the GitHub repo go to **Settings → Secrets and variables → Actions → New repository secret**. Add `SERPER_API_KEY` with its value. Keep the key secret.
4. In **Settings → Pages**, set **Build and deployment → Source: GitHub Actions**. In **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** (required for saving price history). Verify your plan allows Pages/Actions in the chosen repository.
5. Go to **Actions → Hourly iPhone price monitor → Run workflow** to trigger the first run. The job checks the products, commits refreshed data, and publishes the dashboard.
6. Share `https://YOUR-GITHUB-USERNAME.github.io/iphone-price-scout/` with anyone. The page has Share and WhatsApp controls.

The schedule is `17 * * * *` (around minute 17 every hour, UTC). **GitHub may delay or occasionally skip scheduled Actions runs**, so this is an hourly requested cadence, not an SLA. Public repositories' scheduled workflows can also be disabled after prolonged inactivity. Check the repository Actions tab periodically.

## Optional Telegram alerts (you or another person)

1. On Telegram, chat with [@BotFather](https://t.me/BotFather); create a bot and get the bot token.
2. Recipient must **start a chat with the bot** first; otherwise Telegram will reject direct messages. To retrieve their numeric chat ID, use the Telegram Bot API's `getUpdates` endpoint after they send `/start`. Handle bot tokens privately; never paste them into a public file or chat.
3. Add `TELEGRAM_BOT_TOKEN` as a repository **secret**.
4. Add `TELEGRAM_CHAT_IDS` as a repository **variable**: one numeric chat ID, or comma-separated numeric chat IDs for multiple recipients.

By default messages are sent only when an **approved-retailer price drops at least €5 below the previous recorded all-time minimum**, not every hour. To alert whenever a specific price ceiling is first crossed, add optional repository variables `ALERT_PRO_256GB` and/or `ALERT_PRO_MAX_256GB` with euro values, e.g. `1100` and `1250`. Other variants accept `ALERT_PRO_512GB`, `ALERT_PRO_1TB`, `ALERT_PRO_MAX_512GB`, `ALERT_PRO_MAX_1TB`, and `ALERT_PRO_MAX_2TB`. Alerts for first-discovery prices are off by default; toggle `alert_on_first_discovery` in `config.json` if you want an initial baseline message.

Notifications need a valid bot token and recipient chat ID. You can use the dashboard **without Telegram**.

## Usage & estimated search cost

Seven Shopping searches every hour = **168 API searches per day**, or about **5,040 searches per 30 days**. Some Serper Shopping searches may consume more than one credit (e.g. 2 credits); check Serper's *live* consumption and pricing. To reduce cost, edit `storage_gb` in `config.json`, for example `[256]` for each model, which cuts searches to 48/day. Serper's introductory credits may not last a full month if monitoring all seven configurations every hour.

Serper searches Google Shopping listings, which are not a complete registry of all Italian shops and can lag actual prices. The whitelist can be edited in `config.json`. Adding a merchant to the list means you have consciously accepted its trust risk, not that the software has independently vetted it.

## Local test

Requirements: Python 3.12+; no pip packages.

```bash
python -m unittest discover -s tests -v
export SERPER_API_KEY='YOUR_API_KEY'
python src/monitor.py
python -m http.server 8000 --directory docs
# Browse http://localhost:8000
```

On Windows PowerShell use `$env:SERPER_API_KEY="YOUR_API_KEY"` instead of `export`.

The site initially shows **no fictional sample prices**. The first successful live run fills `docs/data/latest.json` and `docs/data/history.json`.

## Source code overview

- `src/monitor.py`: Italian product search, filtering, normalisation, persistent price history, alerts.
- `config.json`: products, retailer allowlist, thresholds, scanning preferences.
- `.github/workflows/monitor.yml`: scheduled checks, history commit, GitHub Pages deployment.
- `docs/index.html`, `docs/style.css`, `docs/app.js`: shareable responsive dashboard.
- `tests/test_monitor.py`: basic protection against mismatched SKUs, unapproved merchants, and price parsing problems.

## Privacy and safety

- Your Serper API key and Telegram bot token remain in GitHub repository Secrets, not in publicly served HTML.
- A public repository and public GitHub Pages site **expose the observed price history** (not the secrets). Do not use the public site for private information.
- The Telegram recipient must opt in by contacting the bot before it can message them.
- Merchant trust classification is conservative but **not a security certification**. Third-party sellers or counterfeit/new-condition claims cannot be conclusively checked through Google Shopping metadata alone.

## Operational caveats

- Google Shopping result links sometimes point to a Google shopping panel rather than directly to a retailer; this is still clickable but requires checking the seller.
- Delivery costs may not be included; the dashboard does not misrepresent unknown shipping as free.
- If a particular model fails its search, its last available data stays visible only with an explicit stale/error status; all-variant failure stops publication.
- When Google Shopping changes its response schema, the monitor may need a code update.

## Faster deployment from Windows (GitHub CLI)

If you have [Git for Windows](https://git-scm.com/downloads/win) and the [GitHub CLI](https://cli.github.com/) installed, extract the ZIP, open PowerShell in the extracted `iphone-price-scout` folder, and run:

```powershell
gh auth login
powershell -ExecutionPolicy Bypass -File .\deploy-windows.ps1
```

The helper creates a **public** GitHub repository, pushes the code, tries to enable GitHub Pages, asks for your `SERPER_API_KEY` securely through `gh secret set`, and requests the first monitor run. If Pages setup or initial workflow dispatch fails, the helper prints the exact GitHub page to finish it manually. Do **not** share your API key with another person; share only the public dashboard link.

If you are deploying through a GitHub organization rather than a personal account, use the manual instructions above.
