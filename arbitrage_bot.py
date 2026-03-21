from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

POLYMARKET_URL = "https://gamma-api.polymarket.com/markets"
KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "cross-arbitrage-bot/0.1",
}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "will",
    "with",
}


@dataclass(frozen=True)
class VenueQuote:
    venue: str
    market_id: str
    title: str
    url: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    last_price: float | None
    volume: float | None = None
    close_time: str | None = None

    @property
    def normalized_title(self) -> str:
        return normalize_market_title(self.title)

    @property
    def mid_price(self) -> float | None:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2
        return self.last_price


@dataclass(frozen=True)
class Opportunity:
    polymarket: VenueQuote
    kalshi: VenueQuote
    strategy: str
    total_cost: float
    locked_in_edge: float
    title_similarity: float
    price_dislocation: float | None


def build_json_opener():
    opener = build_opener(ProxyHandler({}))
    opener.addheaders = list(DEFAULT_HEADERS.items())
    return opener


def fetch_json(url: str, params: dict[str, object] | None = None) -> object:
    opener = build_json_opener()
    query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
    full_url = f"{url}?{query}" if query else url
    try:
        with opener.open(full_url, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while fetching {full_url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching {full_url}: {exc.reason}") from exc


class PolymarketClient:
    def fetch_markets(self, limit: int = 200) -> list[VenueQuote]:
        markets: list[VenueQuote] = []
        offset = 0
        page_size = min(limit, 100)

        while len(markets) < limit:
            payload = fetch_json(
                POLYMARKET_URL,
                {
                    "active": "true",
                    "closed": "false",
                    "limit": page_size,
                    "offset": offset,
                },
            )
            if not isinstance(payload, list) or not payload:
                break

            for item in payload:
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

        if yes_bid is None and yes_ask is None and last_price is None:
            return None

        no_bid = complement(yes_ask)
        no_ask = complement(yes_bid)

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
        )


class KalshiClient:
    def fetch_markets(self, limit: int = 200) -> list[VenueQuote]:
        markets: list[VenueQuote] = []
        cursor: str | None = None
        page_size = min(limit, 100)

        while len(markets) < limit:
            payload = fetch_json(
                KALSHI_URL,
                {
                    "status": "open",
                    "limit": page_size,
                    "cursor": cursor,
                },
            )
            if not isinstance(payload, dict):
                break

            page = payload.get("markets")
            if not isinstance(page, list) or not page:
                break

            for item in page:
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

        yes_bid = parse_probability(
            item.get("yes_bid")
            or item.get("yes_bid_dollars")
            or item.get("yes_bid_price")
        )
        yes_ask = parse_probability(
            item.get("yes_ask")
            or item.get("yes_ask_dollars")
            or item.get("yes_ask_price")
        )
        no_bid = parse_probability(
            item.get("no_bid")
            or item.get("no_bid_dollars")
            or item.get("no_bid_price")
        )
        no_ask = parse_probability(
            item.get("no_ask")
            or item.get("no_ask_dollars")
            or item.get("no_ask_price")
        )
        last_price = parse_probability(
            item.get("last_price")
            or item.get("last_price_dollars")
            or item.get("yes_price")
        )

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
        )


def first_text(item: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_market_title(title: str) -> str:
    lowered = title.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    tokens = [tok for tok in TOKEN_RE.findall(cleaned) if tok not in STOP_WORDS]
    return " ".join(tokens)


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_market_title(left)
    right_norm = normalize_market_title(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(a=left_norm, b=right_norm).ratio()


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


def best_match(target: VenueQuote, candidates: Iterable[VenueQuote]) -> tuple[VenueQuote | None, float]:
    best_quote = None
    best_score = 0.0

    for candidate in candidates:
        score = title_similarity(target.title, candidate.title)
        if score > best_score:
            best_quote = candidate
            best_score = score

    return best_quote, best_score


def detect_opportunities(
    polymarket_quotes: list[VenueQuote],
    kalshi_quotes: list[VenueQuote],
    min_similarity: float = 0.72,
    min_edge: float = 0.02,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []

    for poly in polymarket_quotes:
        kalshi, similarity = best_match(poly, kalshi_quotes)
        if not kalshi or similarity < min_similarity:
            continue

        pairs = [
            ("Buy YES on Polymarket + Buy NO on Kalshi", poly.yes_ask, kalshi.no_ask),
            ("Buy NO on Polymarket + Buy YES on Kalshi", poly.no_ask, kalshi.yes_ask),
        ]

        for strategy, first_leg, second_leg in pairs:
            if first_leg is None or second_leg is None:
                continue
            total_cost = first_leg + second_leg
            locked_in_edge = 1.0 - total_cost
            if locked_in_edge >= min_edge:
                poly_mid = poly.mid_price
                kalshi_mid = kalshi.mid_price
                price_dislocation = (
                    abs(poly_mid - kalshi_mid)
                    if poly_mid is not None and kalshi_mid is not None
                    else None
                )
                opportunities.append(
                    Opportunity(
                        polymarket=poly,
                        kalshi=kalshi,
                        strategy=strategy,
                        total_cost=total_cost,
                        locked_in_edge=locked_in_edge,
                        title_similarity=similarity,
                        price_dislocation=price_dislocation,
                    )
                )

    opportunities.sort(
        key=lambda opp: (opp.locked_in_edge, opp.title_similarity), reverse=True
    )
    return opportunities


def format_probability(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:5.1f}%"


def render_opportunities(opportunities: list[Opportunity], limit: int) -> str:
    if not opportunities:
        return "No cross-exchange opportunities matched the configured thresholds."

    lines = []
    for index, opportunity in enumerate(opportunities[:limit], start=1):
        lines.extend(
            [
                f"[{index}] {opportunity.polymarket.title}",
                f"  Strategy: {opportunity.strategy}",
                f"  Locked-in edge: {opportunity.locked_in_edge * 100:.2f}% | Total cost: {opportunity.total_cost * 100:.2f}% | Title match: {opportunity.title_similarity:.2f}",
                f"  Polymarket YES bid/ask: {format_probability(opportunity.polymarket.yes_bid)} / {format_probability(opportunity.polymarket.yes_ask)}",
                f"  Kalshi YES bid/ask:    {format_probability(opportunity.kalshi.yes_bid)} / {format_probability(opportunity.kalshi.yes_ask)}",
                f"  Polymarket: {opportunity.polymarket.url}",
                f"  Kalshi:     {opportunity.kalshi.url}",
            ]
        )
        if opportunity.price_dislocation is not None:
            lines.append(
                f"  YES mid-price dislocation: {opportunity.price_dislocation * 100:.2f}%"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Display cross-exchange arbitrage opportunities between Polymarket and Kalshi.",
    )
    parser.add_argument("--limit", type=int, default=10, help="maximum opportunities to display")
    parser.add_argument(
        "--markets-per-venue",
        type=int,
        default=200,
        help="how many active/open markets to fetch from each venue",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.72,
        help="minimum title similarity required to match markets",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.02,
        help="minimum locked-in edge to display, expressed as a decimal probability",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.limit <= 0 or args.markets_per_venue <= 0:
        parser.error("--limit and --markets-per-venue must be positive integers")
    if not (0 <= args.min_similarity <= 1):
        parser.error("--min-similarity must be between 0 and 1")
    if not (0 <= args.min_edge <= 1):
        parser.error("--min-edge must be between 0 and 1")

    try:
        polymarket_quotes = PolymarketClient().fetch_markets(limit=args.markets_per_venue)
        kalshi_quotes = KalshiClient().fetch_markets(limit=args.markets_per_venue)
    except RuntimeError as exc:
        print(f"Unable to fetch venue data: {exc}", file=sys.stderr)
        return 1

    opportunities = detect_opportunities(
        polymarket_quotes,
        kalshi_quotes,
        min_similarity=args.min_similarity,
        min_edge=args.min_edge,
    )
    print(render_opportunities(opportunities, limit=args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
