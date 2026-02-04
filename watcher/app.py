import os
import sys
import time
import logging
from dotenv import load_dotenv
from watchdog.observers import Observer
from watcher.watchers import ScreenshotHandler


def main() -> None:
    """Entry point for the media watcher service."""
    # Load env from file if present (compose also injects env)
    load_dotenv()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    handler.flush = sys.stdout.flush
    logger.handlers = [handler]

    screenshot_dir = os.getenv("SCREENSHOT_DIR")

    if not screenshot_dir:
        logger.error("SCREENSHOT_DIR is not set; exiting")
        raise RuntimeError("SCREENSHOT_DIR must be set in the environment")

    screenshot_handler = ScreenshotHandler()

    observer = Observer()
    # Watch recursively to capture screenshots in all per-game subfolders
    observer.schedule(screenshot_handler, screenshot_dir, recursive=True)
    logger.info("Watching %s (recursive)", screenshot_dir)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
