from __future__ import annotations

import time
from uuid import uuid4

from money_printer_lite.alerts import alert_live_order_failure
from money_printer_lite.models import ExecutedTrade, Opportunity
from money_printer_lite.utils import utcnow


class LiveOrderExecutor:
    """
    Minimal, conservative live executor.
    By default this simulates placement unless real API credentials/integration are added.
    """

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def place_orders(self, opportunity: Opportunity, stake: float, retries: int = 2) -> ExecutedTrade:
        now = utcnow()
        if not self.enabled:
            raise RuntimeError("Live execution disabled (LIVE_TRADING=false)")

        attempt = 0
        while True:
            try:
                # Integration point for real Polymarket order placement.
                fill_ratio = 0.6
                realized_pnl = stake * opportunity.net_edge * 0.5
                return ExecutedTrade(
                    trade_id=str(uuid4()),
                    opportunity_id=opportunity.opportunity_id,
                    mode="live",
                    asset=opportunity.asset,
                    setup_type=opportunity.relationship_type,
                    market_ids=opportunity.market_ids,
                    stake=stake * fill_ratio,
                    expected_edge=opportunity.net_edge,
                    realized_pnl=realized_pnl,
                    fill_ratio=fill_ratio,
                    opened_at=now,
                    closed_at=utcnow(),
                )
            except Exception as exc:
                attempt += 1
                alert_live_order_failure(str(exc))
                if attempt > retries:
                    raise
                time.sleep(0.4 * (2**attempt))
