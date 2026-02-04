from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from watcher.config import TelegramConfig


class TelegramSender:
    def __init__(self, config: TelegramConfig) -> None:
        self._bot_token = config.bot_token
        self._chat_id = config.chat_id
        self._send_attempts = config.send_attempts
        self._backoff_seconds = config.backoff_seconds
        self._caption_limit = config.caption_limit
        self._session = requests.Session()

    def send_photo(self, path: str, caption: Optional[str]) -> bool:
        caption = self._truncate_caption(caption)
        for attempt in range(1, self._send_attempts + 1):
            with open(path, "rb") as image:
                resp = self._session.post(
                    f"https://api.telegram.org/bot{self._bot_token}/sendPhoto",
                    data={"chat_id": self._chat_id, "caption": caption} if caption else {"chat_id": self._chat_id},
                    files={"photo": image},
                    timeout=60,
                )
            if resp.status_code == 200:
                return True
            if resp.status_code == 429 or resp.status_code >= 500:
                logging.warning(
                    "Telegram sendPhoto failed (%s), retry %s/%s: %s",
                    resp.status_code,
                    attempt,
                    self._send_attempts,
                    resp.text,
                )
                time.sleep(self._backoff_seconds * attempt)
                continue
            logging.error("Telegram sendPhoto failed (%s): %s", resp.status_code, resp.text)
            return False
        return False

    def _truncate_caption(self, caption: Optional[str]) -> Optional[str]:
        if not caption:
            return None
        if len(caption) <= self._caption_limit:
            return caption
        if self._caption_limit <= 3:
            return caption[: self._caption_limit]
        return caption[: self._caption_limit - 3] + "..."
