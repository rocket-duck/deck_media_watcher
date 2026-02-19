from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from watcher.config import StateConfig


@dataclass(frozen=True)
class PendingItem:
    path: str
    attempt: int
    next_retry_at: float


class SendStateStore:
    def __init__(self, config: StateConfig) -> None:
        self._path = config.file_path
        self._sent_retention_seconds = config.sent_retention_seconds
        self._lock = threading.Lock()
        self._state: Dict[str, dict] = {}
        self._load()

    def mark_discovered(self, path: str) -> bool:
        now = time.time()
        with self._lock:
            item = self._state.get(path)
            if item and item.get("status") == "sent":
                return False
            if item is None:
                self._state[path] = {
                    "status": "pending",
                    "first_seen_at": now,
                    "last_attempt_at": None,
                    "next_retry_at": now,
                    "attempts": 0,
                    "last_error": None,
                    "sent_at": None,
                }
                self._save_locked()
                return True
            if item.get("status") != "pending":
                item["status"] = "pending"
                if item.get("next_retry_at") is None:
                    item["next_retry_at"] = now
                self._save_locked()
            return True

    def mark_sent(self, path: str) -> None:
        now = time.time()
        with self._lock:
            item = self._state.get(path)
            if item is None:
                self._state[path] = {
                    "status": "sent",
                    "first_seen_at": now,
                    "last_attempt_at": now,
                    "next_retry_at": None,
                    "attempts": 1,
                    "last_error": None,
                    "sent_at": now,
                }
            else:
                item["status"] = "sent"
                item["last_attempt_at"] = now
                item["next_retry_at"] = None
                item["last_error"] = None
                item["sent_at"] = now
            self._prune_locked(now)
            self._save_locked()

    def mark_failed(self, path: str, error: str, base_retry_seconds: float, max_retry_seconds: float) -> float:
        now = time.time()
        with self._lock:
            item = self._state.get(path)
            if item is None:
                item = {
                    "status": "pending",
                    "first_seen_at": now,
                    "attempts": 0,
                }
                self._state[path] = item
            attempts = int(item.get("attempts") or 0) + 1
            next_delay = min(max_retry_seconds, base_retry_seconds * max(1, attempts))
            next_retry_at = now + next_delay
            item["status"] = "pending"
            item["attempts"] = attempts
            item["last_attempt_at"] = now
            item["next_retry_at"] = next_retry_at
            item["last_error"] = error
            item["sent_at"] = None
            self._save_locked()
            return next_retry_at

    def get_due_pending(self, now: Optional[float] = None) -> List[PendingItem]:
        if now is None:
            now = time.time()
        with self._lock:
            due: List[PendingItem] = []
            for path, item in self._state.items():
                if item.get("status") != "pending":
                    continue
                next_retry_at = float(item.get("next_retry_at") or 0)
                if next_retry_at <= now:
                    due.append(
                        PendingItem(
                            path=path,
                            attempt=int(item.get("attempts") or 0),
                            next_retry_at=next_retry_at,
                        )
                    )
            return due

    def cleanup_missing(self, known_paths: set[str]) -> int:
        with self._lock:
            removable = [path for path, item in self._state.items() if item.get("status") != "sent" and path not in known_paths]
            if not removable:
                return 0
            for path in removable:
                del self._state[path]
            self._save_locked()
            return len(removable)

    def _load(self) -> None:
        with self._lock:
            self._state = {}
            if not os.path.exists(self._path):
                return
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (OSError, json.JSONDecodeError):
                return
            if isinstance(payload, dict):
                records = payload.get("records")
                if isinstance(records, dict):
                    self._state = records

    def _prune_locked(self, now: float) -> None:
        cutoff = now - self._sent_retention_seconds
        removable = []
        for path, item in self._state.items():
            if item.get("status") != "sent":
                continue
            sent_at = item.get("sent_at")
            if isinstance(sent_at, (int, float)) and sent_at < cutoff:
                removable.append(path)
        for path in removable:
            del self._state[path]

    def _save_locked(self) -> None:
        directory = os.path.dirname(self._path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = {"records": self._state}
        fd, tmp_path = tempfile.mkstemp(prefix=".send_state.", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, ensure_ascii=True, separators=(",", ":"))
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, self._path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
