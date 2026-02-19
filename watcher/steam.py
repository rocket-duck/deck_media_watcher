from __future__ import annotations

from typing import Optional

import requests

from watcher.config import SteamConfig


class SteamResolver:
    def __init__(self, config: SteamConfig) -> None:
        self._lang = config.lang
        self._session = requests.Session()
        self._cache: dict[str, str] = {}

    def resolve_game_name(self, appid: str) -> Optional[str]:
        if appid in self._cache:
            return self._cache[appid]
        try:
            url = "https://store.steampowered.com/api/appdetails"
            params = {"appids": str(appid), "l": self._lang}
            resp = self._session.get(
                url,
                params=params,
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            entry = data.get(str(appid))
            if not entry or not entry.get("success"):
                return None
            name = entry.get("data", {}).get("name")
            if name:
                self._cache[appid] = name
            return name
        except Exception:
            return None

    def close(self) -> None:
        self._session.close()
