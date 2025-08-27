import os
import time
from dotenv import load_dotenv
from watchdog.observers import Observer
from deck_media_watcher.watchers import ScreenshotHandler, VideoHandler


def main() -> None:
    """Entry point for the media watcher service."""
    load_dotenv()

    screenshot_dir = os.getenv("SCREENSHOT_DIR")
    video_dir = os.getenv("VIDEO_DIR")

    if not screenshot_dir or not video_dir:
        raise RuntimeError("SCREENSHOT_DIR and VIDEO_DIR must be set in the environment")

    screenshot_handler = ScreenshotHandler()
    video_handler = VideoHandler()

    observer = Observer()
    observer.schedule(screenshot_handler, screenshot_dir, recursive=False)
    observer.schedule(video_handler, video_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
