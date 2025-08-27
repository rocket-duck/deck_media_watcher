# deck_media_watcher

Service for Steam Deck that monitors the screenshot folder and sends new screenshots to a Telegram chat.

## Configuration

1. Copy `.env.example` to `.env` and fill in the values.
2. Adjust host path to the screenshot directory.

Required variables in `.env`:
- `HOST_SCREENSHOT_DIR` — path on host to Steam Deck screenshots
- `SCREENSHOT_DIR` — mount point inside the container (default `/screenshots`)
- `TELEGRAM_BOT_TOKEN` — your bot token
- `TELEGRAM_CHAT_ID` — chat ID to send screenshots
Optional:
- `STEAM_LANG` — language for game name lookup via Steam store API (default `en`)

## Running with Docker

```bash
docker compose up --build -d
```
The service runs in the background and restarts automatically.
