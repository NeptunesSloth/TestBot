from __future__ import annotations

from money_printer_lite.models import Market
from money_printer_lite.utils import ASSET_RE, RANGE_RE, THRESHOLD_RE, normalize_expiry, parse_price_token, utcnow


def _safe_prob(value: object, fallback: float = 0.5) -> float:
    try:
        num = float(value)
        if num > 1:
            num /= 100.0
        if 0 <= num <= 1:
            return num
    except Exception:
        pass
    return fallback


def discover_crypto_markets(raw_markets: list[dict]) -> list[Market]:
    results: list[Market] = []
    for item in raw_markets:
        question = str(item.get("question") or item.get("title") or "").strip()
        if not question:
            continue
        asset_match = ASSET_RE.search(question)
        if not asset_match:
            continue
        asset = "BTC" if asset_match.group(1).lower() in {"btc", "bitcoin"} else "ETH"

        threshold = None
        threshold_match = THRESHOLD_RE.search(question)
        if threshold_match:
            threshold = parse_price_token(threshold_match.group(1))

        range_low = None
        range_high = None
        range_match = RANGE_RE.search(question)
        if range_match:
            low = parse_price_token(range_match.group(1))
            high = parse_price_token(range_match.group(2))
            range_low, range_high = sorted([low, high])

        yes_bid = _safe_prob(item.get("bestBid"), 0.49)
        yes_ask = _safe_prob(item.get("bestAsk"), 0.51)
        no_bid = max(0.0, 1.0 - yes_ask)
        no_ask = min(1.0, 1.0 - yes_bid)

        results.append(
            Market(
                market_id=str(item.get("id") or item.get("conditionId") or item.get("slug") or question[:36]),
                slug=str(item.get("slug") or ""),
                question=question,
                asset=asset,
                expiry=normalize_expiry(question),
                threshold=threshold,
                range_low=range_low,
                range_high=range_high,
                yes_bid=yes_bid,
                yes_ask=yes_ask,
                no_bid=no_bid,
                no_ask=no_ask,
                volume=float(item.get("volume") or item.get("volumeNum") or 0.0),
                liquidity_hint=float(item.get("liquidity") or item.get("liquidityNum") or item.get("volume") or 0.0),
                updated_at=utcnow(),
            )
        )
    return results
