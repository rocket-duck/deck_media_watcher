from __future__ import annotations

import logging
import os
import threading
import time
from queue import Empty, Queue
from typing import Optional, Tuple

from watchdog.events import FileSystemEventHandler

from watcher.config import (
    DEDUP_TTL_SECONDS,
    FILE_READY_ATTEMPTS,
    FILE_READY_DELAY_SECONDS,
    FILE_READY_MIN_SIZE_BYTES,
    RETRY_INTERVAL_SECONDS,
    SHUTDOWN_DRAIN_SECONDS,
    AppConfig,
)
from watcher.paths import extract_appid_from_path, is_screenshot_file, is_thumbnail_path
from watcher.state import SendStateStore
from watcher.steam import SteamResolver
from watcher.telegram import TelegramSender


class ScreenshotHandler(FileSystemEventHandler):
    """Handle new screenshot files by sending them to Telegram."""

    def __init__(self, config: AppConfig) -> None:
        self._screenshot_dir = config.screenshot_dir
        self._queue: Queue[str] = Queue()
        self._queued_paths: set[str] = set()
        self._queue_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="telegram-sender", daemon=True)
        self._retry_worker = threading.Thread(target=self._retry_loop, name="telegram-retry", daemon=True)
        self._recent: dict[str, float] = {}
        self._state = SendStateStore(config.state)
        self._steam = SteamResolver()
        self._telegram = TelegramSender(config.telegram)
        known_paths = self._discover_existing_screenshots()
        path_mtimes = self._get_mtimes(known_paths)
        self._state.cleanup_missing(known_paths)
        new_count = self._state.preregister_startup(path_mtimes)
        if new_count:
            logging.info("Found %s new screenshots created while stopped, queuing for send", new_count)
        due_items = self._state.get_due_pending()
        for item in due_items:
            if item.path in known_paths:
                self._enqueue(item.path)
        logging.info("Loaded %s existing screenshots for state tracking", len(known_paths))
        self._worker.start()
        self._retry_worker.start()

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        path = event.src_path
        if is_thumbnail_path(path):
            return
        if not is_screenshot_file(path):
            return
        if self._is_duplicate(path):
            return
        if self._state.mark_discovered(path):
            self._enqueue(path)

    def close(self) -> None:
        self._stop_event.set()
        deadline = time.time() + SHUTDOWN_DRAIN_SECONDS
        while time.time() < deadline and not self._queue.empty():
            time.sleep(0.1)
        self._worker.join(timeout=5)
        self._retry_worker.join(timeout=5)
        self._telegram.close()
        self._steam.close()
        self._state.close()

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
                with self._queue_lock:
                    self._queued_paths.discard(path)

    def _retry_loop(self) -> None:
        while not self._stop_event.is_set():
            known_paths = self._discover_existing_screenshots()
            self._state.cleanup_missing(known_paths)
            due_items = self._state.get_due_pending()
            for item in due_items:
                if self._stop_event.is_set():
                    return
                if item.path in known_paths:
                    self._enqueue(item.path)
            self._state.update_heartbeat()
            self._stop_event.wait(RETRY_INTERVAL_SECONDS)

    def _send_screenshot(self, path: str) -> None:
        if not self._wait_until_stable(path):
            logging.warning("File not stable or missing, skipping: %s", path)
            next_retry_at = self._state.mark_failed(path, "file not stable or missing")
            logging.info("Scheduled retry for %s at %.0f", path, next_retry_at)
            return
        caption = self._build_caption(path)
        try:
            ok = self._telegram.send_photo(path, caption)
            if ok:
                self._state.mark_sent(path)
                logging.info(
                    "Sent screenshot: %s%s",
                    os.path.basename(path),
                    f" ({caption})" if caption else "",
                )
            else:
                logging.error("Failed to send screenshot after retries: %s", path)
                next_retry_at = self._state.mark_failed(path, "telegram send returned false")
                logging.info("Scheduled retry for %s at %.0f", path, next_retry_at)
        except Exception as e:
            logging.exception("Failed to send screenshot %s: %s", path, e)
            next_retry_at = self._state.mark_failed(path, str(e))
            logging.info("Scheduled retry for %s at %.0f", path, next_retry_at)

    def _wait_until_stable(self, path: str) -> bool:
        last: Optional[Tuple[int, float]] = None
        for _ in range(FILE_READY_ATTEMPTS):
            if not os.path.exists(path):
                time.sleep(FILE_READY_DELAY_SECONDS)
                continue
            try:
                stat = os.stat(path)
            except OSError:
                time.sleep(FILE_READY_DELAY_SECONDS)
                continue
            current = (stat.st_size, stat.st_mtime)
            if last == current and stat.st_size >= FILE_READY_MIN_SIZE_BYTES:
                return True
            last = current
            time.sleep(FILE_READY_DELAY_SECONDS)
        return False

    def _is_duplicate(self, path: str) -> bool:
        now = time.time()
        cutoff = now - DEDUP_TTL_SECONDS
        if self._recent:
            self._recent = {p: ts for p, ts in self._recent.items() if ts >= cutoff}
        if path in self._recent:
            return True
        self._recent[path] = now
        return False

    def _get_mtimes(self, paths: set[str]) -> dict[str, float]:
        mtimes: dict[str, float] = {}
        for path in paths:
            try:
                mtimes[path] = os.path.getmtime(path)
            except OSError:
                mtimes[path] = 0.0
        return mtimes

    def _discover_existing_screenshots(self) -> set[str]:
        found: set[str] = set()
        for root, dirs, files in os.walk(self._screenshot_dir):
            dirs[:] = [d for d in dirs if d.lower() != "thumbnails"]
            for name in files:
                path = os.path.join(root, name)
                if is_thumbnail_path(path):
                    continue
                if is_screenshot_file(path):
                    found.add(path)
        return found

    def _enqueue(self, path: str) -> None:
        with self._queue_lock:
            if path in self._queued_paths:
                return
            self._queued_paths.add(path)
        self._queue.put(path)
