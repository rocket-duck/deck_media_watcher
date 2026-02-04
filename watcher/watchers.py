import os
import re
import time
import logging
import sys
from typing import Optional

import requests
from watchdog.events import FileSystemEventHandler

class ScreenshotHandler(FileSystemEventHandler):
    """Handle new screenshot files by sending them to Telegram."""

    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        if "thumbnails" in event.src_path.lower().split(os.sep):
            return
        if not event.src_path.lower().endswith((".png", ".jpg", ".jpeg")):
            return
        if not self.bot_token or not self.chat_id:
            return
        path = event.src_path
        # Small delay to ensure file is fully written
        time.sleep(float(os.getenv("FILE_READY_DELAY", "1")))
        caption = self._build_caption(path)
        try:
            with open(path, "rb") as image:
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption} if caption else {"chat_id": self.chat_id},
                    files={"photo": image},
                    timeout=60,
                )
            if resp.status_code != 200:
                logging.error("Telegram sendPhoto failed (%s): %s", resp.status_code, resp.text)
            else:
                logging.info("Sent screenshot: %s%s", os.path.basename(path), f" ({caption})" if caption else "")
        except Exception as e:
            logging.exception("Failed to send screenshot %s: %s", path, e)

    # --- helpers ---------------------------------------------------------
    def _build_caption(self, path: str) -> Optional[str]:
        appid = self._extract_appid_from_path(path)
        if not appid:
            return None
        name = self._resolve_game_name(appid)
        return f"{name}" if name else f"App {appid}"

    def _extract_appid_from_path(self, path: str) -> Optional[str]:
        """
        Steam appid extraction that works both in container and host.

        Ignores:
        - folders like 'thumbnails'
        - folders with numbers < 100 (junk)
        """
        parts = path.split(os.sep)

        def is_valid_appid(value: str) -> bool:
            return value.isdigit() and int(value) >= 100

        # контейнер: /screenshots/<appid>/screenshots/file.jpg
        try:
            if parts[1] == "screenshots" and is_valid_appid(parts[2]) and "thumbnails" not in parts:
                return parts[2]
        except IndexError:
            pass

        try:
            idx = parts.index("remote")
            if is_valid_appid(parts[idx + 1]) and "thumbnails" not in parts:
                return parts[idx + 1]
        except (ValueError, IndexError):
            pass

        return None

    _appid_cache = {}

    def _resolve_game_name(self, appid: str) -> Optional[str]:
        if appid in self._appid_cache:
            return self._appid_cache[appid]
        try:
            lang = os.getenv("STEAM_LANG", "en")
            url = "https://store.steampowered.com/api/appdetails"
            params = {"appids": str(appid), "l": lang}
            resp = requests.get(
                url,
                params=params,
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            entry = data.get(str(appid))
            if not entry or not entry.get("success"):
                return None
            name = entry.get("data", {}).get("name")
            if name:
                self._appid_cache[appid] = name
            return name
        except Exception:
            return None
