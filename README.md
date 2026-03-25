# deck_media_watcher

Service for Steam Deck that monitors the screenshot folder (recursively) and sends new screenshots to a Telegram chat.

## Configuration

Edit `docker-compose.yml` and set the required variables. All other settings are hardcoded constants in `watcher/config.py` — edit there if you need to tune them.

### Required

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Chat ID to send screenshots to |

### Optional

| Variable | Default | Description |
|---|---|---|
| `SCREENSHOT_DIR` | — | Mount point inside the container (set in the `volumes:` section) |
| `STATE_FILE` | `/state/send_state.db` | Path to the persistent state DB |
| `TELEGRAM_PROXY_URL` | *(unset)* | SOCKS5 proxy, e.g. `socks5h://user:pass@host:port` |

### Tunable constants (`watcher/config.py`)

These are not env vars — change the values in source if needed:

| Constant | Default | Description |
|---|---|---|
| `TELEGRAM_SEND_ATTEMPTS` | `3` | Retry attempts per send |
| `TELEGRAM_BACKOFF_SECONDS` | `1` | Base backoff between retries |
| `TELEGRAM_CAPTION_LIMIT` | `1024` | Max caption length (chars) |
| `TELEGRAM_CONNECT_TIMEOUT_SECONDS` | `10` | Connect timeout to Telegram API |
| `TELEGRAM_READ_TIMEOUT_SECONDS` | `60` | Read timeout to Telegram API |
| `RETRY_INTERVAL_SECONDS` | `30` | Base interval for background retries |
| `RETRY_MAX_INTERVAL_SECONDS` | `600` | Max backoff cap for background retries |
| `FILE_READY_DELAY_SECONDS` | `1` | Delay between file stability checks |
| `FILE_READY_ATTEMPTS` | `5` | Stability checks before giving up |
| `FILE_READY_MIN_SIZE_BYTES` | `1024` | Min file size to consider ready |
| `DEDUP_TTL_SECONDS` | `120` | Window to suppress duplicate events |
| `SHUTDOWN_DRAIN_SECONDS` | `5` | Queue drain time on graceful shutdown |
| `STATE_SENT_RETENTION_SECONDS` | `259200` | How long to keep sent records (3 days) |
| `STEAM_LANG` | `en` | Language for Steam game name lookup |
| `STEAM_CC` | `us` | Country code for Steam store API |
| `STEAM_TIMEOUT_SECONDS` | `10` | Timeout for Steam API requests |

## State behavior

- Every screenshot found is tracked in SQLite as `pending` or `sent`.
- On send failure, the screenshot stays `pending` and is retried with **exponential backoff** (`30 → 60 → 120 → 240 → … → 600s`).
- On startup, the watcher scans `SCREENSHOT_DIR` and enqueues all pending items and any screenshots created while the container was stopped.
- If the state file is missing or corrupt, it is moved to `send_state.db.invalid` and a fresh DB is created automatically.
- State persists across container restarts via the `watcher_state:/state` named volume.

## Running with Docker

```bash
docker compose pull
docker compose up -d
```

The service runs in the background and restarts automatically (`restart: unless-stopped`).

## Project Structure

- `watcher/app.py` — entrypoint: loads config, validates env, starts the observer
- `watcher/config.py` — env vars + all tunable constants
- `watcher/handler.py` — event handler, send queue, dedup, file stability check
- `watcher/paths.py` — path utilities (appid extraction, screenshot/thumbnail detection)
- `watcher/steam.py` — Steam Store API lookup with in-memory cache
- `watcher/telegram.py` — Telegram sender with retry and rate-limit handling
- `watcher/state.py` — SQLite state store with exponential backoff scheduling
- `tests/` — pytest test suite
