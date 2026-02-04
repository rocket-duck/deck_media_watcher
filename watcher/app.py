import sys
import time
import logging
from dotenv import load_dotenv
from watchdog.observers import Observer
from watcher.config import load_app_config
from watcher.handler import ScreenshotHandler


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
    logger.handlers = [handler]

    try:
        config = load_app_config()
    except RuntimeError as exc:
        logger.error("%s; exiting", exc)
        raise

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
