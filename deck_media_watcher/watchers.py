import os
import subprocess
import threading
from typing import List

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
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
        with open(event.src_path, "rb") as image:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendPhoto",
                data={"chat_id": self.chat_id},
                files={"photo": image},
                timeout=60,
            )


class VideoHandler(FileSystemEventHandler):
    """Handle new video files by uploading them to YouTube with VPN toggle."""

    _scopes: List[str] = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self) -> None:
        self.vpn_config = os.getenv("VPN_CONFIG", "awg0")
        self.token_file = os.getenv("YOUTUBE_TOKEN_FILE")

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        if not event.src_path.lower().endswith((".mp4", ".webm", ".mkv")):
            return
        if not self.token_file:
            return
        thread = threading.Thread(target=self._process, args=(event.src_path,))
        thread.start()

    # --- Internal helpers -------------------------------------------------
    def _process(self, path: str) -> None:
        self._vpn_up()
        try:
            self._upload(path)
        finally:
            self._vpn_down()

    def _vpn_up(self) -> None:
        subprocess.run(["awg-quick", "up", self.vpn_config], check=True)

    def _vpn_down(self) -> None:
        subprocess.run(["awg-quick", "down", self.vpn_config], check=True)

    def _upload(self, path: str) -> None:
        creds = Credentials.from_authorized_user_file(self.token_file, self._scopes)
        youtube = build("youtube", "v3", credentials=creds)
        body = {"snippet": {"title": os.path.basename(path)}, "status": {"privacyStatus": "private"}}
        media = MediaFileUpload(path, chunksize=-1, resumable=False)
        youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
