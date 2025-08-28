import os
import time
import logging
from dotenv import load_dotenv
from watchdog.observers import Observer
from watcher.watchers import ScreenshotHandler


def main() -> None:
    """Entry point for the media watcher service."""
    # Load env from file if present (compose also injects env)
    load_dotenv()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    screenshot_dir = os.getenv("SCREENSHOT_DIR")

    if not screenshot_dir:
        logging.error("SCREENSHOT_DIR is not set; exiting")
        raise RuntimeError("SCREENSHOT_DIR must be set in the environment")

    screenshot_handler = ScreenshotHandler()

    observer = Observer()
    # Watch recursively to capture screenshots in all per-game subfolders
    observer.schedule(screenshot_handler, screenshot_dir, recursive=True)
    logging.info("Watching %s (recursive)", screenshot_dir)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
