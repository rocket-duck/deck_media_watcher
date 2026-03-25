import os
from unittest.mock import patch

import pytest

from watcher.config import load_app_config


BASE_ENV = {
    "SCREENSHOT_DIR": "/screenshots",
    "TELEGRAM_BOT_TOKEN": "token123",
    "TELEGRAM_CHAT_ID": "456789",
}


class TestLoadAppConfigValidation:
    def test_missing_screenshot_dir_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="SCREENSHOT_DIR"):
                load_app_config()

    def test_missing_bot_token_raises(self):
        env = {"SCREENSHOT_DIR": "/screenshots"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
                load_app_config()

    def test_missing_chat_id_raises(self):
        env = {"SCREENSHOT_DIR": "/screenshots", "TELEGRAM_BOT_TOKEN": "token"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID"):
                load_app_config()


class TestLoadAppConfigValues:
    def test_required_fields_loaded(self):
        with patch.dict(os.environ, BASE_ENV, clear=True):
            config = load_app_config()
        assert config.screenshot_dir == "/screenshots"
        assert config.telegram.bot_token == "token123"
        assert config.telegram.chat_id == "456789"

    def test_proxy_url_none_by_default(self):
        with patch.dict(os.environ, BASE_ENV, clear=True):
            config = load_app_config()
        assert config.telegram.proxy_url is None

    def test_proxy_url_loaded(self):
        env = {**BASE_ENV, "TELEGRAM_PROXY_URL": "socks5h://localhost:1080"}
        with patch.dict(os.environ, env, clear=True):
            config = load_app_config()
        assert config.telegram.proxy_url == "socks5h://localhost:1080"

    def test_state_file_default(self):
        with patch.dict(os.environ, BASE_ENV, clear=True):
            config = load_app_config()
        assert config.state.file_path == "/state/send_state.db"

    def test_state_file_override(self):
        env = {**BASE_ENV, "STATE_FILE": "/tmp/custom.db"}
        with patch.dict(os.environ, env, clear=True):
            config = load_app_config()
        assert config.state.file_path == "/tmp/custom.db"
