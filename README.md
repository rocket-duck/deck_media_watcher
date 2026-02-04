# deck_media_watcher

Service for Steam Deck that monitors the screenshot folder (recursively) and sends new screenshots to a Telegram chat.

## Configuration

1. Copy `.env.example` to `.env` and fill in the values.
2. Adjust host path to the screenshot directory.

Required variables in `.env`:
- `HOST_SCREENSHOT_DIR` — path on host to Steam Deck screenshots (you can point to `.../userdata/<id>/760/remote` to cover all games)
- `SCREENSHOT_DIR` — mount point inside the container (default `/screenshots`)
- `TELEGRAM_BOT_TOKEN` — your bot token
- `TELEGRAM_CHAT_ID` — chat ID to send screenshots
Optional:
- `STEAM_LANG` — language for game name lookup via Steam store API (default `en`)
- `FILE_READY_DELAY` — seconds between file readiness checks (default `1`)
- `FILE_READY_ATTEMPTS` — number of readiness checks before giving up (default `5`)
- `FILE_READY_MIN_SIZE` — minimum file size in bytes to consider ready (default `1024`)
- `DEDUP_TTL_SECONDS` — dedup window to avoid duplicate sends (default `120`)
- `TELEGRAM_SEND_ATTEMPTS` — retry attempts for Telegram send (default `3`)
- `TELEGRAM_SEND_BACKOFF_SECONDS` — base backoff seconds between retries (default `1`)
- `TELEGRAM_CAPTION_LIMIT` — max caption length (default `1024`)
- `SHUTDOWN_DRAIN_SECONDS` — seconds to drain queue on shutdown (default `5`)

## Running with Docker

```bash
docker compose up --build -d
```
The service runs in the background and restarts automatically.

## Project Structure

- `watcher/app.py` — entrypoint: loads config and starts the observer
- `watcher/config.py` — environment config + validation
- `watcher/handler.py` — event handler, queue/worker, dedup, file readiness
- `watcher/paths.py` — path utilities (appid extraction, filters)
- `watcher/steam.py` — Steam API lookup with cache
- `watcher/telegram.py` — Telegram sender with retries
