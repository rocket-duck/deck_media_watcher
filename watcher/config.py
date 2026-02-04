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
class SteamConfig:
    lang: str


@dataclass(frozen=True)
class AppConfig:
    screenshot_dir: str
    telegram: TelegramConfig
    file_ready: FileReadyConfig
    dedup: DedupConfig
    shutdown: ShutdownConfig
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
    steam = SteamConfig(
        lang=os.getenv("STEAM_LANG", "en"),
    )

    return AppConfig(
        screenshot_dir=screenshot_dir,
        telegram=telegram,
        file_ready=file_ready,
        dedup=dedup,
        shutdown=shutdown,
        steam=steam,
    )
