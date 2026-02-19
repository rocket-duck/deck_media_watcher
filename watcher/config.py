from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    send_attempts: int
    backoff_seconds: float
    caption_limit: int
    connect_timeout_seconds: float
    read_timeout_seconds: float


@dataclass(frozen=True)
class FileReadyConfig:
    delay_seconds: float
    attempts: int
    min_size_bytes: int


@dataclass(frozen=True)
class DedupConfig:
    ttl_seconds: float


@dataclass(frozen=True)
class ShutdownConfig:
    drain_seconds: float


@dataclass(frozen=True)
class RetryConfig:
    interval_seconds: float
    max_interval_seconds: float


@dataclass(frozen=True)
class StateConfig:
    file_path: str
    sent_retention_seconds: float


@dataclass(frozen=True)
class SteamConfig:
    lang: str


@dataclass(frozen=True)
class AppConfig:
    screenshot_dir: str
    telegram: TelegramConfig
    file_ready: FileReadyConfig
    dedup: DedupConfig
    shutdown: ShutdownConfig
    retry: RetryConfig
    state: StateConfig
    steam: SteamConfig


def load_app_config() -> AppConfig:
    screenshot_dir = os.getenv("SCREENSHOT_DIR")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not screenshot_dir:
        raise RuntimeError("SCREENSHOT_DIR must be set in the environment")
    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the environment")

    telegram = TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        send_attempts=int(os.getenv("TELEGRAM_SEND_ATTEMPTS", "3")),
        backoff_seconds=float(os.getenv("TELEGRAM_SEND_BACKOFF_SECONDS", "1")),
        caption_limit=int(os.getenv("TELEGRAM_CAPTION_LIMIT", "1024")),
        connect_timeout_seconds=float(os.getenv("TELEGRAM_CONNECT_TIMEOUT_SECONDS", "10")),
        read_timeout_seconds=float(os.getenv("TELEGRAM_READ_TIMEOUT_SECONDS", "60")),
    )
    file_ready = FileReadyConfig(
        delay_seconds=float(os.getenv("FILE_READY_DELAY", "1")),
        attempts=int(os.getenv("FILE_READY_ATTEMPTS", "5")),
        min_size_bytes=int(os.getenv("FILE_READY_MIN_SIZE", "1024")),
    )
    dedup = DedupConfig(
        ttl_seconds=float(os.getenv("DEDUP_TTL_SECONDS", "120")),
    )
    shutdown = ShutdownConfig(
        drain_seconds=float(os.getenv("SHUTDOWN_DRAIN_SECONDS", "5")),
    )
    retry = RetryConfig(
        interval_seconds=float(os.getenv("RETRY_INTERVAL_SECONDS", "30")),
        max_interval_seconds=float(os.getenv("RETRY_MAX_INTERVAL_SECONDS", "600")),
    )
    state = StateConfig(
        file_path=os.getenv("STATE_FILE", "/state/send_state.json"),
        sent_retention_seconds=float(os.getenv("STATE_SENT_RETENTION_SECONDS", "259200")),
    )
    steam = SteamConfig(
        lang=os.getenv("STEAM_LANG", "en"),
    )

    return AppConfig(
        screenshot_dir=screenshot_dir,
        telegram=telegram,
        file_ready=file_ready,
        dedup=dedup,
        shutdown=shutdown,
        retry=retry,
        state=state,
        steam=steam,
    )
