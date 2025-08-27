import os
import time
from dotenv import load_dotenv
from watchdog.observers import Observer
from watcher.watchers import ScreenshotHandler


def main() -> None:
    """Entry point for the media watcher service."""
    load_dotenv()

    screenshot_dir = os.getenv("SCREENSHOT_DIR")

    if not screenshot_dir:
        raise RuntimeError("SCREENSHOT_DIR must be set in the environment")

    screenshot_handler = ScreenshotHandler()

    observer = Observer()
    observer.schedule(screenshot_handler, screenshot_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
