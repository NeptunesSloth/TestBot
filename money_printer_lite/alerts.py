from __future__ import annotations

import logging

from money_printer_lite.models import Opportunity


logger = logging.getLogger("alerts")


def alert_new_opportunity(opportunity: Opportunity) -> None:
    logger.info(
        "ALERT opportunity %s asset=%s type=%s net_edge=%.4f confidence=%.2f",
        opportunity.opportunity_id,
        opportunity.asset,
        opportunity.relationship_type,
        opportunity.net_edge,
        opportunity.confidence_score,
    )


def alert_high_confidence(opportunity: Opportunity) -> None:
    logger.warning(
        "HIGH-CONFIDENCE opportunity %s net_edge=%.4f depth=%.2f",
        opportunity.opportunity_id,
        opportunity.net_edge,
        opportunity.order_book_depth,
    )


def alert_live_order_failure(message: str) -> None:
    logger.error("LIVE-ORDER-FAILURE %s", message)


def alert_stale_data(seconds: int) -> None:
    logger.warning("STALE-DATA data age is %ss", seconds)
