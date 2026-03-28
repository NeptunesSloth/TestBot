from __future__ import annotations

from collections import defaultdict

from money_printer_lite.models import Market, MarketGroup


def build_groups(markets: list[Market]) -> list[MarketGroup]:
    grouped: dict[tuple[str, str], list[Market]] = defaultdict(list)
    for market in markets:
        grouped[(market.asset, market.expiry)].append(market)

    result: list[MarketGroup] = []
    for (asset, expiry), items in grouped.items():
        gid = f"{asset}-{expiry}"
        result.append(MarketGroup(group_id=gid, asset=asset, expiry=expiry, markets=items))
    return result
