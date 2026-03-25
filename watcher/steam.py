from __future__ import annotations

import logging
from typing import Optional

import requests

from watcher.config import STEAM_CC, STEAM_LANG, STEAM_TIMEOUT_SECONDS


class SteamResolver:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._cache: dict[str, str] = {}

    def resolve_game_name(self, appid: str) -> Optional[str]:
        if appid in self._cache:
            return self._cache[appid]
        try:
            resp = self._session.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": str(appid), "l": STEAM_LANG, "cc": STEAM_CC},
                timeout=STEAM_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logging.warning("Steam appdetails non-200 for appid=%s: status=%s", appid, resp.status_code)
                return None
            data = resp.json()
            entry = data.get(str(appid))
            if not entry or not entry.get("success"):
                logging.info("Steam appdetails unresolved for appid=%s (lang=%s, cc=%s)", appid, STEAM_LANG, STEAM_CC)
                return None
            name = entry.get("data", {}).get("name")
            if name:
                self._cache[appid] = name
            else:
                logging.info("Steam appdetails has no name for appid=%s (lang=%s, cc=%s)", appid, STEAM_LANG, STEAM_CC)
            return name
        except Exception as exc:
            logging.exception("Steam appdetails request failed for appid=%s: %s", appid, exc)
            return None

    def close(self) -> None:
        self._session.close()
