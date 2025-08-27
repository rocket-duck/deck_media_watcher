# deck_media_watcher

Service for Steam Deck that monitors screenshot and video folders. When new screenshots appear they are sent to a Telegram chat, and new videos are uploaded to YouTube through AmneziaWG VPN.

## Configuration

1. Copy `.env.example` to `.env` and fill in the values.
2. Place your YouTube OAuth token file on the host and set its path in `.env`.
3. Adjust host paths to screenshot and video directories.

## Running with Docker

```bash
docker compose up --build -d
```
The service runs in the background and restarts automatically.
