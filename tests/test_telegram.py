from unittest.mock import MagicMock, patch

import pytest

from watcher.config import TELEGRAM_CAPTION_LIMIT, TelegramConfig
from watcher.telegram import TelegramSender


@pytest.fixture
def sender():
    config = TelegramConfig(bot_token="test_token", chat_id="123456", proxy_url=None)
    s = TelegramSender(config)
    yield s
    s.close()


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(b"x" * 2048)
    return str(p)


class TestSendPhoto:
    def test_success_returns_true(self, sender, photo):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(sender._session, "post", return_value=mock_resp):
            assert sender.send_photo(photo, "Half-Life") is True

    def test_4xx_returns_false_immediately(self, sender, photo):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        with patch.object(sender._session, "post", return_value=mock_resp):
            assert sender.send_photo(photo, "Half-Life") is False

    def test_retries_on_429_then_fails(self, sender, photo):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Too Many Requests"
        mock_resp.json.return_value = {}
        with patch.object(sender._session, "post", return_value=mock_resp):
            with patch("watcher.telegram.time.sleep"):  # skip actual sleep
                assert sender.send_photo(photo, "Half-Life") is False

    def test_retries_on_500_then_fails(self, sender, photo):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.json.return_value = {}
        with patch.object(sender._session, "post", return_value=mock_resp):
            with patch("watcher.telegram.time.sleep"):
                assert sender.send_photo(photo, "Half-Life") is False

    def test_retries_on_500_succeeds_on_second(self, sender, photo):
        fail_resp = MagicMock(status_code=500, text="err")
        fail_resp.json.return_value = {}
        ok_resp = MagicMock(status_code=200)
        with patch.object(sender._session, "post", side_effect=[fail_resp, ok_resp]):
            with patch("watcher.telegram.time.sleep"):
                assert sender.send_photo(photo, "Half-Life") is True

    def test_uses_retry_after_header(self, sender, photo):
        fail_resp = MagicMock(status_code=429, text="rate limited")
        fail_resp.json.return_value = {"parameters": {"retry_after": 5}}
        ok_resp = MagicMock(status_code=200)
        slept = []
        with patch.object(sender._session, "post", side_effect=[fail_resp, ok_resp]):
            with patch("watcher.telegram.time.sleep", side_effect=lambda s: slept.append(s)):
                sender.send_photo(photo, "Half-Life")
        assert slept == [5.0]

    def test_no_caption_sends_without_caption_field(self, sender, photo):
        mock_resp = MagicMock(status_code=200)
        with patch.object(sender._session, "post", return_value=mock_resp) as mock_post:
            sender.send_photo(photo, None)
        call_data = mock_post.call_args.kwargs["data"]
        assert "caption" not in call_data


class TestTruncateCaption:
    def test_short_caption_unchanged(self, sender):
        assert sender._truncate_caption("Short") == "Short"

    def test_long_caption_truncated_with_ellipsis(self, sender):
        long = "A" * (TELEGRAM_CAPTION_LIMIT + 100)
        result = sender._truncate_caption(long)
        assert len(result) == TELEGRAM_CAPTION_LIMIT
        assert result.endswith("...")

    def test_none_returns_none(self, sender):
        assert sender._truncate_caption(None) is None

    def test_empty_string_returns_none(self, sender):
        assert sender._truncate_caption("") is None
