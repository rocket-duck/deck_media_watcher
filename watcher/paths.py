import os
from typing import Optional


def is_thumbnail_path(path: str) -> bool:
    return "thumbnails" in path.lower().split(os.sep)


def is_screenshot_file(path: str) -> bool:
    return path.lower().endswith((".png", ".jpg", ".jpeg"))


def extract_appid_from_path(path: str) -> Optional[str]:
    """
    Steam appid extraction that works both in container and host.

    Ignores:
    - folders like 'thumbnails'
    - folders with numbers < 100 (junk)
    """
    parts = path.split(os.sep)

    def is_valid_appid(value: str) -> bool:
        return value.isdigit() and int(value) >= 100

    # контейнер: /screenshots/<appid>/screenshots/file.jpg
    try:
        if parts[1] == "screenshots" and is_valid_appid(parts[2]) and "thumbnails" not in parts:
            return parts[2]
    except IndexError:
        pass

    try:
        idx = parts.index("remote")
        if is_valid_appid(parts[idx + 1]) and "thumbnails" not in parts:
            return parts[idx + 1]
    except (ValueError, IndexError):
        pass

    return None
