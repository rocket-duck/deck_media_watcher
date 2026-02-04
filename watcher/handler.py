from __future__ import annotations

import logging
import os
import threading
import time
from queue import Empty, Queue
from typing import Optional, Tuple

from watchdog.events import FileSystemEventHandler

from watcher.config import AppConfig
from watcher.paths import extract_appid_from_path, is_screenshot_file, is_thumbnail_path
from watcher.steam import SteamResolver
from watcher.telegram import TelegramSender


class ScreenshotHandler(FileSystemEventHandler):
    """Handle new screenshot files by sending them to Telegram."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._queue: Queue[str] = Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="telegram-sender", daemon=True)
        self._recent: dict[str, float] = {}
        self._recent_ttl = config.dedup.ttl_seconds
        self._steam = SteamResolver(config.steam)
        self._telegram = TelegramSender(config.telegram)
        self._worker.start()

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        if is_thumbnail_path(event.src_path):
            return
        if not is_screenshot_file(event.src_path):
            return
        path = event.src_path
        if self._is_duplicate(path):
            return
        self._queue.put(path)

    def close(self) -> None:
        drain_timeout = self._config.shutdown.drain_seconds
        self._stop_event.set()
        deadline = time.time() + drain_timeout
        while time.time() < deadline and not self._queue.empty():
            time.sleep(0.1)
        self._worker.join(timeout=5)

    # --- helpers ---------------------------------------------------------
    def _build_caption(self, path: str) -> Optional[str]:
        appid = extract_appid_from_path(path)
        if not appid:
            return None
        name = self._steam.resolve_game_name(appid)
        return f"{name}" if name else f"App {appid}"

    def _worker_loop(self) -> None:
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                break
            try:
                path = self._queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._send_screenshot(path)
            finally:
                self._queue.task_done()

    def _send_screenshot(self, path: str) -> None:
        if not self._wait_until_stable(path):
            logging.warning("File not stable or missing, skipping: %s", path)
            return
        caption = self._build_caption(path)
        try:
            ok = self._telegram.send_photo(path, caption)
            if ok:
                logging.info(
                    "Sent screenshot: %s%s",
                    os.path.basename(path),
                    f" ({caption})" if caption else "",
                )
        except Exception as e:
            logging.exception("Failed to send screenshot %s: %s", path, e)

    def _wait_until_stable(self, path: str) -> bool:
        delay = self._config.file_ready.delay_seconds
        attempts = self._config.file_ready.attempts
        min_size = self._config.file_ready.min_size_bytes
        last: Optional[Tuple[int, float]] = None
        for _ in range(attempts):
            if not os.path.exists(path):
                time.sleep(delay)
                continue
            try:
                stat = os.stat(path)
            except OSError:
                time.sleep(delay)
                continue
            current = (stat.st_size, stat.st_mtime)
            if last == current and stat.st_size >= min_size:
                return True
            last = current
            time.sleep(delay)
        return False

    def _is_duplicate(self, path: str) -> bool:
        now = time.time()
        cutoff = now - self._recent_ttl
        if self._recent:
            self._recent = {p: ts for p, ts in self._recent.items() if ts >= cutoff}
        if path in self._recent:
            return True
        self._recent[path] = now
        return False
