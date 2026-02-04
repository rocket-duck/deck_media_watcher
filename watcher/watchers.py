import os
import re
import time
import logging
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
        time.sleep(float(os.getenv("FILE_READY_DELAY", "0.5")))
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
        # Common Steam path: .../userdata/<user>/760/remote/<appid>/screenshots/XXXX.jpg
        m = re.search(r"/remote/(\d{1,10})/screenshots/", path)
        if m:
            return m.group(1)
        return None

    def _resolve_game_name(self, appid: str) -> Optional[str]:
        try:
            lang = os.getenv("STEAM_LANG", "en")
            resp = requests.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": appid, "l": lang},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            entry = data.get(appid)
            if not entry or not entry.get("success"):
                return None
            name = entry.get("data", {}).get("name")
            return name
        except Exception:
            return None
