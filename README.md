# deck_media_watcher

Service for Steam Deck that monitors the screenshot folder (recursively) and sends new screenshots to a Telegram chat.

## Configuration

Fill in the environment variables directly in `docker-compose.yml` and set the host path to the screenshot directory.

Required variables:
- `SCREENSHOT_DIR` — mount point inside the container (default `/screenshots`)
- `TELEGRAM_BOT_TOKEN` — your bot token
- `TELEGRAM_CHAT_ID` — chat ID to send screenshots
Optional:
- `STEAM_LANG` — language for game name lookup via Steam store API (default `en`)
- `STATE_FILE` — path to persistent send state file (default `/state/send_state.json`)
- `STATE_SENT_RETENTION_SECONDS` — how long to keep `sent` records in state (default `259200`, 3 days)
- `FILE_READY_DELAY` — seconds between file readiness checks (default `1`)
- `FILE_READY_ATTEMPTS` — number of readiness checks before giving up (default `5`)
- `FILE_READY_MIN_SIZE` — minimum file size in bytes to consider ready (default `1024`)
- `DEDUP_TTL_SECONDS` — dedup window to avoid duplicate sends (default `120`)
- `TELEGRAM_SEND_ATTEMPTS` — retry attempts for Telegram send (default `3`)
- `TELEGRAM_SEND_BACKOFF_SECONDS` — base backoff seconds between retries (default `1`)
- `TELEGRAM_CAPTION_LIMIT` — max caption length (default `1024`)
- `TELEGRAM_CONNECT_TIMEOUT_SECONDS` — connect timeout to Telegram API (default `10`)
- `TELEGRAM_READ_TIMEOUT_SECONDS` — read timeout to Telegram API (default `60`)
- `RETRY_INTERVAL_SECONDS` — base interval for background retries of unsent screenshots (default `30`)
- `RETRY_MAX_INTERVAL_SECONDS` — max backoff interval for background retries (default `600`)
- `SHUTDOWN_DRAIN_SECONDS` — seconds to drain queue on shutdown (default `5`)

State behavior:
- Every found screenshot is tracked in local state (`pending` / `sent`).
- If send fails, screenshot stays `pending` and is retried periodically in background.
- On container startup, watcher scans `SCREENSHOT_DIR` and enqueues all pending screenshots from state.
- To persist state across container recreation, keep `STATE_FILE` on a mounted volume (see `docker-compose.yml` with `watcher_state:/state`).

## Running with Docker

```bash
docker compose pull
docker compose up -d
```
The service runs in the background and restarts automatically.


## Project Structure

- `watcher/app.py` — entrypoint: loads config and starts the observer
- `watcher/config.py` — environment config + validation
- `watcher/handler.py` — event handler, queue/worker, dedup, file readiness
- `watcher/paths.py` — path utilities (appid extraction, filters)
- `watcher/steam.py` — Steam API lookup with cache
- `watcher/telegram.py` — Telegram sender with retries
- `watcher/state.py` — persistent send state storage and pending retry metadata
