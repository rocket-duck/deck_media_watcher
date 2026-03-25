from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from requests import Response
from requests.exceptions import RequestException

from watcher.config import (
    TELEGRAM_BACKOFF_SECONDS,
    TELEGRAM_CAPTION_LIMIT,
    TELEGRAM_CONNECT_TIMEOUT_SECONDS,
    TELEGRAM_READ_TIMEOUT_SECONDS,
    TELEGRAM_SEND_ATTEMPTS,
    TelegramConfig,
)


class TelegramSender:
    def __init__(self, config: TelegramConfig) -> None:
        self._chat_id = config.chat_id
        self._session = requests.Session()
        if config.proxy_url:
            self._session.proxies = {"http": config.proxy_url, "https": config.proxy_url}
            logging.info("Telegram sender using proxy: %s", config.proxy_url)
        self._url = f"https://api.telegram.org/bot{config.bot_token}/sendPhoto"

    def send_photo(self, path: str, caption: Optional[str]) -> bool:
        caption = self._truncate_caption(caption)
        payload = {"chat_id": self._chat_id, "caption": caption} if caption else {"chat_id": self._chat_id}
        for attempt in range(1, TELEGRAM_SEND_ATTEMPTS + 1):
            try:
                with open(path, "rb") as image:
                    resp = self._session.post(
                        self._url,
                        data=payload,
                        files={"photo": image},
                        timeout=(TELEGRAM_CONNECT_TIMEOUT_SECONDS, TELEGRAM_READ_TIMEOUT_SECONDS),
                    )
            except RequestException as exc:
                if attempt == TELEGRAM_SEND_ATTEMPTS:
                    logging.error(
                        "Telegram sendPhoto failed on final attempt %s/%s due to network error: %s",
                        attempt,
                        TELEGRAM_SEND_ATTEMPTS,
                        exc,
                    )
                    return False
                self._log_and_backoff(attempt, f"network error: {exc}")
                continue
            if resp.status_code == 200:
                return True
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == TELEGRAM_SEND_ATTEMPTS:
                    logging.error(
                        "Telegram sendPhoto failed on final attempt %s/%s (%s): %s",
                        attempt,
                        TELEGRAM_SEND_ATTEMPTS,
                        resp.status_code,
                        resp.text,
                    )
                    return False
                wait = self._retry_after_from_response(resp) or TELEGRAM_BACKOFF_SECONDS * attempt
                self._log_and_backoff(attempt, f"HTTP {resp.status_code}: {resp.text}", wait_seconds=wait)
                continue
            logging.error("Telegram sendPhoto failed (%s): %s", resp.status_code, resp.text)
            return False
        return False

    def close(self) -> None:
        self._session.close()

    def _log_and_backoff(self, attempt: int, reason: str, wait_seconds: Optional[float] = None) -> None:
        delay = TELEGRAM_BACKOFF_SECONDS * attempt if wait_seconds is None else wait_seconds
        logging.warning(
            "Telegram sendPhoto failed, retry %s/%s in %.2fs: %s",
            attempt,
            TELEGRAM_SEND_ATTEMPTS,
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
        if len(caption) <= TELEGRAM_CAPTION_LIMIT:
            return caption
        if TELEGRAM_CAPTION_LIMIT <= 3:
            return caption[:TELEGRAM_CAPTION_LIMIT]
        return caption[: TELEGRAM_CAPTION_LIMIT - 3] + "..."
