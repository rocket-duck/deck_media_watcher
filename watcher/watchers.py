import os
import re
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
        if not event.src_path.lower().endswith((".png", ".jpg", ".jpeg")):
            return
        if not self.bot_token or not self.chat_id:
            return
        caption = self._build_caption(event.src_path)
        with open(event.src_path, "rb") as image:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendPhoto",
                data={"chat_id": self.chat_id, "caption": caption} if caption else {"chat_id": self.chat_id},
                files={"photo": image},
                timeout=60,
            )

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
