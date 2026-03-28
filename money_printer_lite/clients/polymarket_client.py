from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener


class PolymarketClient:
    def __init__(self, fixture_path: str | None = None):
        self.fixture_path = fixture_path

    def fetch_markets(self, limit: int = 250) -> list[dict]:
        if self.fixture_path:
            payload = json.loads(Path(self.fixture_path).read_text())
            return payload[:limit]
        opener = build_opener(ProxyHandler({}))
        url = "https://gamma-api.polymarket.com/markets"
        query = urlencode({"active": "true", "closed": "false", "limit": limit, "offset": 0})
        full_url = f"{url}?{query}"
        try:
            with opener.open(full_url, timeout=20) as response:
                payload = json.load(response)
            if isinstance(payload, list):
                return payload
            return []
        except HTTPError as exc:
            raise RuntimeError(f"Polymarket HTTP error {exc.code}: {full_url}") from exc
        except URLError as exc:
            raise RuntimeError(f"Polymarket network error: {exc.reason}") from exc
