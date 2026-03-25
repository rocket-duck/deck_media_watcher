import json
import logging
import os
import sys
import time

from watchdog.observers import Observer

from watcher.config import load_app_config
from watcher.handler import ScreenshotHandler


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


def main() -> None:
    """Entry point for the media watcher service."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(_JsonFormatter())
    logger.handlers = [handler]

    try:
        config = load_app_config()
    except RuntimeError as exc:
        logger.error("%s; exiting", exc)
        raise

    if not os.path.isdir(config.screenshot_dir):
        logger.error("SCREENSHOT_DIR does not exist or is not a directory: %s; exiting", config.screenshot_dir)
        sys.exit(1)

    screenshot_handler = ScreenshotHandler(config)

    observer = Observer()
    # Watch recursively to capture screenshots in all per-game subfolders
    observer.schedule(screenshot_handler, config.screenshot_dir, recursive=True)
    logger.info("Watching %s (recursive)", config.screenshot_dir)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        screenshot_handler.close()
    observer.join()
