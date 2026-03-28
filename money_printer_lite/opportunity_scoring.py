from __future__ import annotations

from money_printer_lite.config import BotConfig
from money_printer_lite.models import Opportunity


def score_opportunity(opportunity: Opportunity, cfg: BotConfig) -> Opportunity:
    fee = opportunity.gross_edge * cfg.fee_rate
    slippage = (cfg.slippage_bps / 10000.0) * (1.0 - min(1.0, opportunity.order_book_depth / 5000.0))
    fill_quality = min(1.0, opportunity.order_book_depth / max(cfg.min_depth, 1.0))
    net_edge = opportunity.gross_edge - fee - slippage
    confidence = max(0.0, min(1.0, 0.5 * fill_quality + 0.5 * (net_edge / max(cfg.min_net_edge, 1e-6))))

    opportunity.estimated_fees = fee
    opportunity.estimated_slippage = slippage
    opportunity.estimated_fill_quality = fill_quality
    opportunity.net_edge = net_edge
    opportunity.confidence_score = confidence
    opportunity.qualifies_for_paper = net_edge >= cfg.min_net_edge and opportunity.order_book_depth >= cfg.min_depth
    opportunity.qualifies_for_live = (
        net_edge >= cfg.min_net_edge * 1.25
        and opportunity.order_book_depth >= cfg.min_depth * 1.5
        and confidence >= cfg.high_confidence_threshold
    )
    return opportunity
