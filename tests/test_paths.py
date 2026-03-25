import pytest
from watcher.paths import extract_appid_from_path, is_screenshot_file, is_thumbnail_path


class TestIsThumbnailPath:
    def test_detects_thumbnails_segment(self):
        assert is_thumbnail_path("/screenshots/730/thumbnails/file.jpg") is True

    def test_case_insensitive(self):
        assert is_thumbnail_path("/screenshots/730/Thumbnails/file.jpg") is True

    def test_normal_path_is_not_thumbnail(self):
        assert is_thumbnail_path("/screenshots/730/screenshots/file.jpg") is False

    def test_filename_containing_thumbnails_word(self):
        # Only path segments count, not partial filename matches
        assert is_thumbnail_path("/screenshots/730/my_thumbnails_backup/file.jpg") is False


class TestIsScreenshotFile:
    @pytest.mark.parametrize("ext", [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"])
    def test_image_extensions(self, ext):
        assert is_screenshot_file(f"file{ext}") is True

    @pytest.mark.parametrize("ext", [".txt", ".mp4", ".db", ".json", ""])
    def test_non_image_extensions(self, ext):
        assert is_screenshot_file(f"file{ext}") is False


class TestExtractAppidFromPath:
    def test_container_path(self):
        assert extract_appid_from_path("/screenshots/730/screenshots/shot.png") == "730"

    def test_host_path_with_remote(self):
        path = "/home/user/.local/share/Steam/userdata/12345/760/remote/730/screenshots/shot.png"
        assert extract_appid_from_path(path) == "730"

    def test_ignores_appid_below_minimum(self):
        # App ID 99 is below MIN_STEAM_APP_ID=100
        assert extract_appid_from_path("/screenshots/99/screenshots/shot.png") is None

    def test_minimum_valid_appid(self):
        assert extract_appid_from_path("/screenshots/100/screenshots/shot.png") == "100"

    def test_thumbnail_path_returns_none(self):
        assert extract_appid_from_path("/screenshots/730/thumbnails/shot.png") is None

    def test_no_match_returns_none(self):
        assert extract_appid_from_path("/some/random/path/file.png") is None

    def test_non_numeric_segment_returns_none(self):
        assert extract_appid_from_path("/screenshots/abc/screenshots/shot.png") is None
