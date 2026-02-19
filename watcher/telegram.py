from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from requests import Response
from requests.exceptions import RequestException

from watcher.config import TelegramConfig


class TelegramSender:
    def __init__(self, config: TelegramConfig) -> None:
        self._bot_token = config.bot_token
        self._chat_id = config.chat_id
        self._send_attempts = config.send_attempts
        self._backoff_seconds = config.backoff_seconds
        self._caption_limit = config.caption_limit
        self._connect_timeout = config.connect_timeout_seconds
        self._read_timeout = config.read_timeout_seconds
        self._session = requests.Session()
        self._url = f"https://api.telegram.org/bot{self._bot_token}/sendPhoto"

    def send_photo(self, path: str, caption: Optional[str]) -> bool:
        caption = self._truncate_caption(caption)
        payload = {"chat_id": self._chat_id, "caption": caption} if caption else {"chat_id": self._chat_id}
        for attempt in range(1, self._send_attempts + 1):
            try:
                with open(path, "rb") as image:
                    resp = self._session.post(
                        self._url,
                        data=payload,
                        files={"photo": image},
                        timeout=(self._connect_timeout, self._read_timeout),
                    )
            except RequestException as exc:
                if attempt == self._send_attempts:
                    logging.error(
                        "Telegram sendPhoto failed on final attempt %s/%s due to network error: %s",
                        attempt,
                        self._send_attempts,
                        exc,
                    )
                    return False
                self._log_and_backoff_on_error(attempt, f"network error: {exc}")
                continue
            if resp.status_code == 200:
                return True
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self._send_attempts:
                    logging.error(
                        "Telegram sendPhoto failed on final attempt %s/%s (%s): %s",
                        attempt,
                        self._send_attempts,
                        resp.status_code,
                        resp.text,
                    )
                    return False
                wait_seconds = self._retry_after_from_response(resp) or self._backoff_seconds * attempt
                self._log_and_backoff_on_error(
                    attempt,
                    f"HTTP {resp.status_code}: {resp.text}",
                    wait_seconds=wait_seconds,
                )
                continue
            logging.error("Telegram sendPhoto failed (%s): %s", resp.status_code, resp.text)
            return False
        return False

    def close(self) -> None:
        self._session.close()

    def _log_and_backoff_on_error(self, attempt: int, reason: str, wait_seconds: Optional[float] = None) -> None:
        delay = self._backoff_seconds * attempt if wait_seconds is None else wait_seconds
        logging.warning(
            "Telegram sendPhoto failed, retry %s/%s in %.2fs: %s",
            attempt,
            self._send_attempts,
            delay,
            reason,
        )
        time.sleep(delay)

    def _retry_after_from_response(self, resp: Response) -> Optional[float]:
        try:
            payload = resp.json()
        except ValueError:
            return None
        retry_after = payload.get("parameters", {}).get("retry_after")
        if isinstance(retry_after, int) and retry_after >= 0:
            return float(retry_after)
        return None

    def _truncate_caption(self, caption: Optional[str]) -> Optional[str]:
        if not caption:
            return None
        if len(caption) <= self._caption_limit:
            return caption
        if self._caption_limit <= 3:
            return caption[: self._caption_limit]
        return caption[: self._caption_limit - 3] + "..."
