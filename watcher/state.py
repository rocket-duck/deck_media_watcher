from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from watcher.config import (
    RETRY_INTERVAL_SECONDS,
    RETRY_MAX_INTERVAL_SECONDS,
    StateConfig,
)


@dataclass(frozen=True)
class PendingItem:
    path: str
    attempt: int
    next_retry_at: float


class SendStateStore:
    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS screenshots (
            path TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            first_seen_at REAL,
            last_attempt_at REAL,
            next_retry_at REAL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            sent_at REAL
        )
    """
    _CREATE_META = """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """
    _CREATE_INDEX = """
        CREATE INDEX IF NOT EXISTS idx_status_retry
        ON screenshots (status, next_retry_at)
    """

    def __init__(self, config: StateConfig) -> None:
        self._path = config.file_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._conn = self._open_connection()
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute(self._CREATE_TABLE)
            self._conn.execute(self._CREATE_META)
            self._conn.execute(self._CREATE_INDEX)
            self._conn.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('created_at', ?)",
                (str(time.time()),),
            )
        row = self._conn.execute("SELECT value FROM metadata WHERE key='created_at'").fetchone()
        self._db_created_at = float(row["value"])

        hb_row = self._conn.execute("SELECT value FROM metadata WHERE key='last_shutdown_at'").fetchone()
        self._startup_cutoff: float = float(hb_row["value"]) if hb_row else self._db_created_at
        self.update_heartbeat()

        self._migrate_from_json()

    def _open_connection(self) -> sqlite3.Connection:
        """Open SQLite connection, renaming the file if it is not a valid database."""
        try:
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")  # probe validity
            return conn
        except sqlite3.DatabaseError:
            backup = self._path + ".invalid"
            logging.warning(
                "State file %s is not a valid SQLite database, moving to %s and starting fresh",
                self._path,
                backup,
            )
            try:
                os.replace(self._path, backup)
            except OSError as e:
                logging.error("Could not move invalid state file: %s", e)
            return sqlite3.connect(self._path, check_same_thread=False)

    def _migrate_from_json(self) -> None:
        base = os.path.splitext(self._path)[0]
        json_path = base + ".json"
        if not os.path.exists(json_path):
            return
        count = self._conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0]
        if count > 0:
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            records = payload.get("records", {})
            if not isinstance(records, dict):
                return
            rows = [
                (
                    path,
                    item.get("status", "pending"),
                    item.get("first_seen_at"),
                    item.get("last_attempt_at"),
                    item.get("next_retry_at"),
                    item.get("attempts", 0),
                    item.get("last_error"),
                    item.get("sent_at"),
                )
                for path, item in records.items()
            ]
            with self._conn:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO screenshots VALUES (?,?,?,?,?,?,?,?)",
                    rows,
                )
            logging.info("Migrated %d records from %s to SQLite", len(rows), json_path)
            os.rename(json_path, json_path + ".migrated")
        except Exception as e:
            logging.warning("Failed to migrate from JSON state: %s", e)

    def mark_discovered(self, path: str) -> bool:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM screenshots WHERE path = ?", (path,)
            ).fetchone()
            if row and row["status"] == "sent":
                return False
            if row is None:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO screenshots (path, status, first_seen_at, next_retry_at, attempts) VALUES (?, 'pending', ?, ?, 0)",
                        (path, now, now),
                    )
                return True
            if row["status"] != "pending":
                with self._conn:
                    self._conn.execute(
                        "UPDATE screenshots SET status='pending', next_retry_at=COALESCE(next_retry_at, ?) WHERE path=?",
                        (now, path),
                    )
            return True

    def mark_sent(self, path: str) -> None:
        now = time.time()
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO screenshots (path, status, first_seen_at, last_attempt_at, attempts, sent_at)
                       VALUES (?, 'sent', ?, ?, 1, ?)
                       ON CONFLICT(path) DO UPDATE SET
                           status='sent', last_attempt_at=excluded.last_attempt_at,
                           next_retry_at=NULL, last_error=NULL, sent_at=excluded.sent_at""",
                    (path, now, now, now),
                )

    def mark_failed(self, path: str, error: str) -> float:
        """Mark a screenshot as failed and schedule exponential-backoff retry.

        Returns the absolute timestamp of the next retry.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT attempts FROM screenshots WHERE path = ?", (path,)
            ).fetchone()
            attempts = (int(row["attempts"]) if row else 0) + 1
            delay = RETRY_INTERVAL_SECONDS * (2 ** (attempts - 1))
            next_retry_at = now + min(RETRY_MAX_INTERVAL_SECONDS, delay)
            with self._conn:
                self._conn.execute(
                    """INSERT INTO screenshots (path, status, first_seen_at, last_attempt_at, next_retry_at, attempts, last_error)
                       VALUES (?, 'pending', ?, ?, ?, ?, ?)
                       ON CONFLICT(path) DO UPDATE SET
                           status='pending', last_attempt_at=excluded.last_attempt_at,
                           next_retry_at=excluded.next_retry_at, attempts=excluded.attempts,
                           last_error=excluded.last_error, sent_at=NULL""",
                    (path, now, now, next_retry_at, attempts, error),
                )
            return next_retry_at

    def get_due_pending(self, now: Optional[float] = None) -> List[PendingItem]:
        if now is None:
            now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, attempts, next_retry_at FROM screenshots WHERE status='pending' AND next_retry_at <= ?",
                (now,),
            ).fetchall()
            return [
                PendingItem(path=r["path"], attempt=int(r["attempts"]), next_retry_at=float(r["next_retry_at"] or 0))
                for r in rows
            ]

    def cleanup_missing(self, known_paths: set[str]) -> int:
        with self._lock:
            rows = self._conn.execute(
                "SELECT path FROM screenshots"
            ).fetchall()
            removable = [r["path"] for r in rows if r["path"] not in known_paths]
            if not removable:
                return 0
            with self._conn:
                self._conn.executemany(
                    "DELETE FROM screenshots WHERE path = ?",
                    [(p,) for p in removable],
                )
            return len(removable)

    def preregister_startup(self, path_mtimes: dict[str, float]) -> int:
        """Register unknown files on startup based on mtime vs DB creation time.

        Files older than DB → mark as sent (existed before tracking started).
        Files newer than DB → mark as pending (created while container was down).
        Returns count of files marked as pending (will be sent).
        """
        now = time.time()
        with self._lock:
            existing = {
                r["path"]
                for r in self._conn.execute("SELECT path FROM screenshots").fetchall()
            }
            sent_rows = []
            pending_rows = []
            for path, mtime in path_mtimes.items():
                if path in existing:
                    continue
                if mtime < self._startup_cutoff:
                    sent_rows.append((path, "sent", mtime, now, None, 0, None, now))
                else:
                    pending_rows.append((path, "pending", mtime, None, now, 0, None, None))
            insert_sql = "INSERT OR IGNORE INTO screenshots VALUES (?,?,?,?,?,?,?,?)"
            with self._conn:
                if sent_rows:
                    self._conn.executemany(insert_sql, sent_rows)
                if pending_rows:
                    self._conn.executemany(insert_sql, pending_rows)
            return len(pending_rows)

    def update_heartbeat(self) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_shutdown_at', ?)",
                    (str(time.time()),),
                )

    def close(self) -> None:
        self.update_heartbeat()
        self._conn.close()

