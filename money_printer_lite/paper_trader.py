from __future__ import annotations

from uuid import uuid4

from money_printer_lite.models import ExecutedTrade, Opportunity
from money_printer_lite.utils import utcnow


def simulate_fill_ratio(depth: float, min_depth: float) -> float:
    if min_depth <= 0:
        return 1.0
    return max(0.1, min(1.0, depth / (min_depth * 1.2)))


def execute_paper_trade(opportunity: Opportunity, stake: float, min_depth: float) -> ExecutedTrade:
    fill_ratio = simulate_fill_ratio(opportunity.order_book_depth, min_depth)
    effective_stake = stake * fill_ratio
    # conservative pnl realization: only realize a fraction of expected edge
    realized_edge = opportunity.net_edge * (0.4 + 0.6 * fill_ratio)
    realized_pnl = effective_stake * realized_edge
    now = utcnow()
    return ExecutedTrade(
        trade_id=str(uuid4()),
        opportunity_id=opportunity.opportunity_id,
        mode="paper",
        asset=opportunity.asset,
        setup_type=opportunity.relationship_type,
        market_ids=opportunity.market_ids,
        stake=effective_stake,
        expected_edge=opportunity.net_edge,
        realized_pnl=realized_pnl,
        fill_ratio=fill_ratio,
        opened_at=now,
        closed_at=now,
    )
