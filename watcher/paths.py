import os
from typing import Optional

# Steam app IDs below this value are considered invalid/junk folders
MIN_STEAM_APP_ID = 100


def is_thumbnail_path(path: str) -> bool:
    return "thumbnails" in path.lower().split(os.sep)


def is_screenshot_file(path: str) -> bool:
    return path.lower().endswith((".png", ".jpg", ".jpeg"))


def extract_appid_from_path(path: str) -> Optional[str]:
    """
    Steam appid extraction that works both in container and host.

    Ignores:
    - folders like 'thumbnails'
    - folders with numbers < MIN_STEAM_APP_ID (junk)
    """
    parts = path.split(os.sep)

    def is_valid_appid(value: str) -> bool:
        return value.isdigit() and int(value) >= MIN_STEAM_APP_ID

    # Container path: /screenshots/<appid>/screenshots/file.jpg
    try:
        if parts[1] == "screenshots" and is_valid_appid(parts[2]) and "thumbnails" not in parts:
            return parts[2]
    except IndexError:
        pass

    # Host path: .../remote/<appid>/screenshots/file.jpg
    try:
        idx = parts.index("remote")
        if is_valid_appid(parts[idx + 1]) and "thumbnails" not in parts:
            return parts[idx + 1]
    except (ValueError, IndexError):
        pass

    return None
