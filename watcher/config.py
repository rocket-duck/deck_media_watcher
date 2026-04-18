from __future__ import annotations

import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tunable constants — change here to adjust behaviour without env vars
# ---------------------------------------------------------------------------

# File stability detection
FILE_READY_DELAY_SECONDS: float = 1.0
FILE_READY_ATTEMPTS: int = 5
FILE_READY_MIN_SIZE_BYTES: int = 1024

# In-memory dedup window (seconds before the same path can be re-queued)
DEDUP_TTL_SECONDS: float = 120.0

# Graceful shutdown: how long to wait for the send queue to drain
SHUTDOWN_DRAIN_SECONDS: float = 5.0

# Background retry scheduler
RETRY_INTERVAL_SECONDS: float = 30.0
RETRY_MAX_INTERVAL_SECONDS: float = 600.0

# Steam Store API
STEAM_LANG: str = "en"
STEAM_CC: str = "us"
STEAM_TIMEOUT_SECONDS: float = 10.0

# Telegram sender
TELEGRAM_SEND_ATTEMPTS: int = 3
TELEGRAM_BACKOFF_SECONDS: float = 1.0
TELEGRAM_CAPTION_LIMIT: int = 1024
TELEGRAM_CONNECT_TIMEOUT_SECONDS: float = 10.0
TELEGRAM_READ_TIMEOUT_SECONDS: float = 60.0

# ---------------------------------------------------------------------------
# Config objects — only fields that come from environment variables
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    proxy_url: str | None


@dataclass(frozen=True)
class StateConfig:
    file_path: str


@dataclass(frozen=True)
class AppConfig:
    screenshot_dir: str
    telegram: TelegramConfig
    state: StateConfig


def load_app_config() -> AppConfig:
    screenshot_dir = os.getenv("SCREENSHOT_DIR")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not screenshot_dir:
        raise RuntimeError("SCREENSHOT_DIR must be set in the environment")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in the environment")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID must be set in the environment")

    return AppConfig(
        screenshot_dir=screenshot_dir,
        telegram=TelegramConfig(
            bot_token=bot_token,
            chat_id=chat_id,
            proxy_url=os.getenv("TELEGRAM_PROXY_URL") or None,
        ),
        state=StateConfig(
            file_path=os.getenv("STATE_FILE", "/state/send_state.db"),
        ),
    )
