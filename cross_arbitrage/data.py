from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from .core import ScanResult, VenueQuote, detect_opportunities

POLYMARKET_URL = "https://gamma-api.polymarket.com/markets"
KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "cross-arbitrage-bot/0.2",
}
BUNDLED_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def build_json_opener():
    opener = build_opener(ProxyHandler({}))
    opener.addheaders = list(DEFAULT_HEADERS.items())
    return opener


def fetch_json(url: str, params: dict[str, object] | None = None) -> object:
    opener = build_json_opener()
    query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
    full_url = f"{url}?{query}" if query else url
    try:
        with opener.open(full_url, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while fetching {full_url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching {full_url}: {exc.reason}") from exc


def parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_probability(value: object) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if number > 1.0:
        number /= 100.0
    if 0.0 <= number <= 1.0:
        return number
    return None


def complement(probability: float | None) -> float | None:
    if probability is None:
        return None
    return round(1.0 - probability, 6)


def first_text(item: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_listish(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        if value:
            return [part.strip() for part in value.split(",") if part.strip()]
    return []


class LivePolymarketClient:
    def fetch_markets(self, limit: int) -> list[VenueQuote]:
        markets: list[VenueQuote] = []
        offset = 0
        page_size = min(limit, 100)
        while len(markets) < limit:
            payload = fetch_json(
                POLYMARKET_URL,
                {"active": "true", "closed": "false", "limit": page_size, "offset": offset},
            )
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if isinstance(item, dict):
                    quote = self._parse_market(item)
                    if quote:
                        markets.append(quote)
                        if len(markets) >= limit:
                            break
            if len(payload) < page_size:
                break
            offset += page_size
        return markets

    def _parse_market(self, item: dict[str, object]) -> VenueQuote | None:
        title = first_text(item, "question", "title")
        slug = first_text(item, "slug")
        if not title or not slug:
            return None

        yes_bid = parse_probability(item.get("bestBid"))
        yes_ask = parse_probability(item.get("bestAsk"))
        last_price = parse_probability(item.get("lastTradePrice"))

        outcomes = [token.lower() for token in parse_listish(item.get("outcomes"))]
        outcome_prices = [parse_probability(token) for token in parse_listish(item.get("outcomePrices"))]
        if len(outcomes) == 2 and len(outcome_prices) == 2 and "yes" in outcomes and "no" in outcomes:
            yes_index = outcomes.index("yes")
            no_index = outcomes.index("no")
            fallback_yes = outcome_prices[yes_index]
            fallback_no = outcome_prices[no_index]
            yes_bid = yes_bid if yes_bid is not None else fallback_yes
            yes_ask = yes_ask if yes_ask is not None else fallback_yes
            no_bid = complement(yes_ask) if fallback_no is None else fallback_no
            no_ask = complement(yes_bid) if fallback_no is None else fallback_no
        else:
            no_bid = complement(yes_ask)
            no_ask = complement(yes_bid)

        if yes_bid is None and yes_ask is None and last_price is None:
            return None
        return VenueQuote(
            venue="Polymarket",
            market_id=str(item.get("id") or slug),
            title=title,
            url=f"https://polymarket.com/event/{slug}",
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            last_price=last_price,
            volume=parse_float(item.get("volume") or item.get("volumeNum")),
            close_time=first_text(item, "endDate", "end_date", "closedTime"),
            metadata={"source": "live"},
        )


class LiveKalshiClient:
    def fetch_markets(self, limit: int) -> list[VenueQuote]:
        markets: list[VenueQuote] = []
        cursor: str | None = None
        page_size = min(limit, 100)
        while len(markets) < limit:
            payload = fetch_json(KALSHI_URL, {"status": "open", "limit": page_size, "cursor": cursor})
            if not isinstance(payload, dict):
                break
            page = payload.get("markets")
            if not isinstance(page, list) or not page:
                break
            for item in page:
                if isinstance(item, dict):
                    quote = self._parse_market(item)
                    if quote:
                        markets.append(quote)
                        if len(markets) >= limit:
                            break
            cursor = payload.get("cursor") or None
            if not cursor or len(page) < page_size:
                break
        return markets

    def _parse_market(self, item: dict[str, object]) -> VenueQuote | None:
        title = first_text(item, "title")
        ticker = first_text(item, "ticker")
        if not title or not ticker:
            return None
        yes_bid = parse_probability(item.get("yes_bid") or item.get("yes_bid_dollars") or item.get("yes_bid_price"))
        yes_ask = parse_probability(item.get("yes_ask") or item.get("yes_ask_dollars") or item.get("yes_ask_price"))
        no_bid = parse_probability(item.get("no_bid") or item.get("no_bid_dollars") or item.get("no_bid_price"))
        no_ask = parse_probability(item.get("no_ask") or item.get("no_ask_dollars") or item.get("no_ask_price"))
        last_price = parse_probability(item.get("last_price") or item.get("last_price_dollars") or item.get("yes_price"))
        if yes_bid is None and yes_ask is None and last_price is None:
            return None
        return VenueQuote(
            venue="Kalshi",
            market_id=ticker,
            title=title,
            url=f"https://kalshi.com/markets/{ticker}",
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            last_price=last_price,
            volume=parse_float(item.get("volume") or item.get("volume_dollars")),
            close_time=first_text(item, "close_date", "expiration_time", "settlement_date"),
            metadata={"source": "live"},
        )


class FixturePolymarketClient(LivePolymarketClient):
    def __init__(self, fixture_path: str | Path | None = None):
        self.fixture_path = Path(fixture_path) if fixture_path else BUNDLED_FIXTURE_DIR / "polymarket_markets.json"

    def fetch_markets(self, limit: int) -> list[VenueQuote]:
        payload = json.loads(self.fixture_path.read_text())
        markets = []
        for item in payload[:limit]:
            quote = self._parse_market(item)
            if quote:
                markets.append(
                    VenueQuote(
                        **{**quote.__dict__, "metadata": {**quote.metadata, "source": "fixture"}}
                    )
                )
        return markets


class FixtureKalshiClient(LiveKalshiClient):
    def __init__(self, fixture_path: str | Path | None = None):
        self.fixture_path = Path(fixture_path) if fixture_path else BUNDLED_FIXTURE_DIR / "kalshi_markets.json"

    def fetch_markets(self, limit: int) -> list[VenueQuote]:
        payload = json.loads(self.fixture_path.read_text())
        page = payload.get("markets", [])
        markets = []
        for item in page[:limit]:
            quote = self._parse_market(item)
            if quote:
                markets.append(
                    VenueQuote(
                        **{**quote.__dict__, "metadata": {**quote.metadata, "source": "fixture"}}
                    )
                )
        return markets


def run_scan(
    mode: str,
    markets_per_venue: int,
    min_similarity: float,
    min_edge: float,
    polymarket_fixture: str | None = None,
    kalshi_fixture: str | None = None,
) -> ScanResult:
    warning = None
    source_mode = mode

    if mode == "mock":
        poly_client = FixturePolymarketClient(polymarket_fixture)
        kalshi_client = FixtureKalshiClient(kalshi_fixture)
    elif mode == "live":
        poly_client = LivePolymarketClient()
        kalshi_client = LiveKalshiClient()
    elif mode == "auto":
        try:
            poly_client = LivePolymarketClient()
            kalshi_client = LiveKalshiClient()
            poly_quotes = poly_client.fetch_markets(markets_per_venue)
            kalshi_quotes = kalshi_client.fetch_markets(markets_per_venue)
            opportunities = detect_opportunities(poly_quotes, kalshi_quotes, min_similarity=min_similarity, min_edge=min_edge)
            return ScanResult(opportunities, len(poly_quotes), len(kalshi_quotes), "live")
        except RuntimeError as exc:
            poly_client = FixturePolymarketClient(polymarket_fixture)
            kalshi_client = FixtureKalshiClient(kalshi_fixture)
            warning = f"Live venue fetch failed and bundled fixtures were used instead: {exc}"
            source_mode = "mock-fallback"
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    try:
        poly_quotes = poly_client.fetch_markets(markets_per_venue)
        kalshi_quotes = kalshi_client.fetch_markets(markets_per_venue)
        opportunities = detect_opportunities(poly_quotes, kalshi_quotes, min_similarity=min_similarity, min_edge=min_edge)
        return ScanResult(opportunities, len(poly_quotes), len(kalshi_quotes), source_mode, warning=warning)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        return ScanResult([], 0, 0, source_mode, warning=warning, error=f"Unable to fetch venue data: {exc}")
