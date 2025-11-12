# Yad2 Monitor

Chrome-extension powered Yad2 housing search monitor backed by a FastAPI service, SQLite persistence, and Telegram notifications.

## What it does
- Detects active Yad2 search result URLs directly from the browser
- Registers per-user scraping jobs that persist to SQLite instead of ad-hoc JSON files
- Sends Telegram notifications for new listings, price drops, and price changes
- Generates unique `/start` deep links so users can subscribe to the bot in one click
- Stores listings per user, ensuring each preference operates in isolation

## Repository layout
- `main.py` – FastAPI application entrypoint
- `app/` – backend code (config, models, services, API routes)
- `extension/` – Chrome extension (manifest, background worker, popup UI)
- `yad_scrapper.py` – stealth scraper used by monitoring workers

## Prerequisites
- Python 3.10+
- Chrome/Chromium for the extension
- A Telegram bot token (create via [@BotFather](https://t.me/BotFather))

## Backend setup
1. Create and activate a virtual environment (example using `uv`):
   ```bash
   uv venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   uv pip install -e .
   ```
3. Copy `.env.example` to `.env` and populate at least `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`.
4. Start the API (workers and Telegram poller boot with the server):
   ```bash
   uvicorn main:app --reload
   ```
5. The API exposes:
   - `GET /health`
   - `POST /api/v1/users/register`
   - `GET /api/v1/users/{user_id}/status`

The service automatically spins up monitoring threads for every active preference stored in SQLite on startup.

### Telegram integration notes
- The server uses long-polling via `getUpdates`; ensure no webhook is registered for the bot (`deleteWebhook` via BotFather if needed).
- When a user registers, the API returns a deep link like `https://t.me/<bot>?start=<token>`.
- The included poller watches for `/start <token>` and stores the chat ID so notifications can flow.

## Chrome extension
1. In Chrome, open `chrome://extensions` and toggle **Developer mode**.
2. Click **Load unpacked** and select the `extension/` directory.
3. Optionally open the extension options page to point it to a non-default API base URL.
4. Browse to a Yad2 results page (e.g., “Rent” filters). The extension detects the URL, shows the parsed parameters in the popup, and lets you submit registration details.
5. After registering, click the Telegram link the popup displays and press **Start** in Telegram to finish the subscription.

## Data storage
- Data folder defaults to `./data/yad2_monitor.db` (override with env vars `DATA_DIR`, `SQLITE_DB_FILENAME`).
- `users`, `search_preferences`, and `listings` tables keep per-user state.
- New or changed listings are queued and stored until a Telegram chat is connected, ensuring no missed notifications.

## Development tips
- Run FastAPI with `uvicorn` and inspect logs for scraper output.
- Use `sqlite3 data/yad2_monitor.db` or a GUI client to inspect stored listings.
- Extension badge “ON” indicates an active Yad2 tab has been detected.
- Modify `extension/manifest.json` host permissions when deploying against a remote API host.

## Testing the flow locally
1. Launch the backend (`uvicorn main:app --reload`).
2. Load the extension.
3. Visit a Yad2 search results page.
4. Use the popup to register with your Telegram username.
5. Click the returned deep link and press **Start** in Telegram.
6. Wait for monitoring messages or manually trigger scraper iterations by adjusting `check_interval_minutes` via API.

## Roadmap ideas
- Add user-facing dashboard for listing history and manual resend of pending notifications.
- Support push infrastructure for the extension (websocket events) to reflect real-time status.
- Expose admin APIs for pausing/resuming preferences and for removing stale listings automatically.
- Persist Telegram update offsets in the database for resilience across restarts.
