from __future__ import annotations

from itertools import combinations
from uuid import uuid4

from money_printer_lite.config import BotConfig
from money_printer_lite.models import Market, MarketGroup, Opportunity
from money_printer_lite.opportunity_scoring import score_opportunity
from money_printer_lite.utils import utcnow


def _classify(gross_edge: float, bounded: bool) -> str:
    if bounded and gross_edge > 0.02:
        return "true_arbitrage"
    if gross_edge > 0.01:
        return "near_arbitrage"
    return "mispricing"


def detect_monotonicity(group: MarketGroup, cfg: BotConfig) -> list[Opportunity]:
    thresholds = [m for m in group.markets if m.threshold is not None]
    thresholds.sort(key=lambda m: m.threshold or 0.0)
    opportunities: list[Opportunity] = []

    for easier, harder in combinations(thresholds, 2):
        # easier condition probability should be >= harder
        violation = harder.yes_ask - easier.yes_bid
        if violation <= 0:
            continue
        depth = min(easier.liquidity_hint, harder.liquidity_hint)
        gross = violation
        opp = Opportunity(
            opportunity_id=str(uuid4()),
            detected_at=utcnow(),
            relationship_type="monotonicity",
            opportunity_class=_classify(gross, bounded=True),
            asset=group.asset,
            group_id=group.group_id,
            market_ids=[easier.market_id, harder.market_id],
            description=f"Monotonicity violation: easier '{easier.question}' priced below harder '{harder.question}'",
            gross_edge=gross,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            estimated_fill_quality=0.0,
            order_book_depth=depth,
            net_edge=0.0,
            max_theoretical_profit=max(0.0, gross),
            max_theoretical_loss=max(0.0, 1.0 - gross),
            confidence_score=0.0,
            qualifies_for_paper=False,
            qualifies_for_live=False,
        )
        opportunities.append(score_opportunity(opp, cfg))
    return opportunities


def detect_bucket_mispricing(group: MarketGroup, cfg: BotConfig) -> list[Opportunity]:
    buckets = [m for m in group.markets if m.range_low is not None and m.range_high is not None]
    opportunities: list[Opportunity] = []
    if len(buckets) < 2:
        return opportunities

    total = sum(m.yes_ask for m in buckets)
    if total < 1.0 - cfg.min_net_edge / 2:
        gross = 1.0 - total
        depth = min(m.liquidity_hint for m in buckets)
        opp = Opportunity(
            opportunity_id=str(uuid4()),
            detected_at=utcnow(),
            relationship_type="bucket",
            opportunity_class=_classify(gross, bounded=True),
            asset=group.asset,
            group_id=group.group_id,
            market_ids=[m.market_id for m in buckets],
            description=f"Bucket underpricing sum(YES asks)={total:.3f} < 1.000",
            gross_edge=gross,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            estimated_fill_quality=0.0,
            order_book_depth=depth,
            net_edge=0.0,
            max_theoretical_profit=gross,
            max_theoretical_loss=max(0.0, 1.0 - gross),
            confidence_score=0.0,
            qualifies_for_paper=False,
            qualifies_for_live=False,
        )
        opportunities.append(score_opportunity(opp, cfg))

    if total > 1.0 + cfg.min_net_edge / 2:
        gross = total - 1.0
        depth = min(m.liquidity_hint for m in buckets)
        opp = Opportunity(
            opportunity_id=str(uuid4()),
            detected_at=utcnow(),
            relationship_type="bucket",
            opportunity_class=_classify(gross, bounded=True),
            asset=group.asset,
            group_id=group.group_id,
            market_ids=[m.market_id for m in buckets],
            description=f"Bucket overpricing sum(YES asks)={total:.3f} > 1.000",
            gross_edge=gross,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            estimated_fill_quality=0.0,
            order_book_depth=depth,
            net_edge=0.0,
            max_theoretical_profit=gross,
            max_theoretical_loss=max(0.0, 1.0 - gross),
            confidence_score=0.0,
            qualifies_for_paper=False,
            qualifies_for_live=False,
        )
        opportunities.append(score_opportunity(opp, cfg))

    return opportunities


def detect_complements(group: MarketGroup, cfg: BotConfig) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    thresholds = [m for m in group.markets if m.threshold is not None]
    for left, right in combinations(thresholds, 2):
        # rough near-complement: similar threshold and opposing language can be absent in text;
        # we conservatively require tiny threshold difference.
        if left.threshold is None or right.threshold is None:
            continue
        if abs(left.threshold - right.threshold) > max(250.0, 0.005 * left.threshold):
            continue
        total = left.yes_ask + right.no_ask
        gross = abs(1.0 - total)
        if gross < cfg.min_net_edge / 2:
            continue
        depth = min(left.liquidity_hint, right.liquidity_hint)
        opp = Opportunity(
            opportunity_id=str(uuid4()),
            detected_at=utcnow(),
            relationship_type="complement",
            opportunity_class=_classify(gross, bounded=False),
            asset=group.asset,
            group_id=group.group_id,
            market_ids=[left.market_id, right.market_id],
            description=f"Near-complement divergence around threshold {left.threshold:,.0f}",
            gross_edge=gross,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            estimated_fill_quality=0.0,
            order_book_depth=depth,
            net_edge=0.0,
            max_theoretical_profit=gross,
            max_theoretical_loss=1.0,
            confidence_score=0.0,
            qualifies_for_paper=False,
            qualifies_for_live=False,
        )
        opportunities.append(score_opportunity(opp, cfg))
    return opportunities


def detect_opportunities(groups: list[MarketGroup], cfg: BotConfig) -> list[Opportunity]:
    all_opps: list[Opportunity] = []
    for group in groups:
        all_opps.extend(detect_monotonicity(group, cfg))
        all_opps.extend(detect_bucket_mispricing(group, cfg))
        all_opps.extend(detect_complements(group, cfg))

    all_opps.sort(key=lambda o: (o.net_edge, o.confidence_score, o.order_book_depth), reverse=True)
    return all_opps
