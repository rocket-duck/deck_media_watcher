import time

import pytest

from watcher.config import RETRY_INTERVAL_SECONDS, StateConfig
from watcher.state import SendStateStore


@pytest.fixture
def store(tmp_path):
    s = SendStateStore(StateConfig(file_path=str(tmp_path / "state.db")))
    yield s
    s.close()


class TestMarkDiscovered:
    def test_new_path_returns_true(self, store):
        assert store.mark_discovered("/screenshots/730/shot.png") is True

    def test_already_pending_returns_true(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        assert store.mark_discovered("/screenshots/730/shot.png") is True

    def test_sent_path_returns_false(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        store.mark_sent("/screenshots/730/shot.png")
        assert store.mark_discovered("/screenshots/730/shot.png") is False


class TestMarkSent:
    def test_removes_from_pending(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        store.mark_sent("/screenshots/730/shot.png")
        # Force next_retry_at to past so it would appear in due list
        store._conn.execute("UPDATE screenshots SET next_retry_at = 0")
        store._conn.commit()
        due = store.get_due_pending()
        assert not any(item.path == "/screenshots/730/shot.png" for item in due)


class TestMarkFailed:
    def test_schedules_retry_in_future(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        before = time.time()
        next_retry = store.mark_failed("/screenshots/730/shot.png", "test error")
        assert next_retry > before

    def test_exponential_backoff_grows(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        t0 = time.time()
        r = [store.mark_failed("/screenshots/730/shot.png", "err") for _ in range(4)]
        # delays from t0: should roughly follow 30, 60, 120, 240
        delays = [ri - t0 for ri in r]
        assert delays[1] > delays[0] * 1.5
        assert delays[2] > delays[1] * 1.5
        assert delays[3] > delays[2] * 1.5

    def test_capped_at_max_interval(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        # Run many failures to hit the cap
        for _ in range(20):
            store.mark_failed("/screenshots/730/shot.png", "err")
        t0 = time.time()
        next_retry = store.mark_failed("/screenshots/730/shot.png", "err")
        # Should not exceed max interval by more than a small tolerance
        from watcher.config import RETRY_MAX_INTERVAL_SECONDS
        assert next_retry - t0 <= RETRY_MAX_INTERVAL_SECONDS + 1


class TestGetDuePending:
    def test_returns_overdue_item(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        store._conn.execute("UPDATE screenshots SET next_retry_at = 0")
        store._conn.commit()
        due = store.get_due_pending()
        assert any(item.path == "/screenshots/730/shot.png" for item in due)

    def test_does_not_return_future_item(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        future = time.time() + 9999
        store._conn.execute("UPDATE screenshots SET next_retry_at = ?", (future,))
        store._conn.commit()
        due = store.get_due_pending()
        assert not any(item.path == "/screenshots/730/shot.png" for item in due)


class TestCleanupMissing:
    def test_removes_pending_not_on_disk(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        removed = store.cleanup_missing(set())
        assert removed == 1

    def test_keeps_sent_even_if_missing_on_disk(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        store.mark_sent("/screenshots/730/shot.png")
        removed = store.cleanup_missing(set())
        assert removed == 0

    def test_keeps_known_pending(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        removed = store.cleanup_missing({"/screenshots/730/shot.png"})
        assert removed == 0


class TestPreregisterStartup:
    def test_new_file_marked_pending(self, store):
        future_mtime = store._db_created_at + 10
        count = store.preregister_startup({"/screenshots/730/new.png": future_mtime})
        assert count == 1

    def test_old_file_marked_sent(self, store):
        old_mtime = store._db_created_at - 10
        count = store.preregister_startup({"/screenshots/730/old.png": old_mtime})
        assert count == 0  # not pending

    def test_already_known_file_skipped(self, store):
        store.mark_discovered("/screenshots/730/shot.png")
        future_mtime = store._db_created_at + 10
        count = store.preregister_startup({"/screenshots/730/shot.png": future_mtime})
        assert count == 0
