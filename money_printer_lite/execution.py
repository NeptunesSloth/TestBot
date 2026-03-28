from __future__ import annotations

from money_printer_lite.config import BotConfig
from money_printer_lite.models import Opportunity, TradeDecision


class RiskGuard:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.market_exposure: dict[str, float] = {}
        self.total_exposure = 0.0

    def can_trade(self, opportunity: Opportunity, stake: float, mode: str) -> tuple[bool, str]:
        if self.cfg.kill_switch:
            return False, "kill switch enabled"
        if mode == "live" and not self.cfg.live_trading:
            return False, "LIVE_TRADING is not enabled"
        if stake > self.cfg.max_position_size:
            return False, "stake exceeds max position size"
        if self.total_exposure + stake > self.cfg.total_exposure_cap:
            return False, "total exposure cap breached"
        for market_id in opportunity.market_ids:
            if self.market_exposure.get(market_id, 0.0) + stake > self.cfg.per_market_exposure_cap:
                return False, f"per-market exposure cap breached for {market_id}"
        return True, "ok"

    def register_trade(self, opportunity: Opportunity, stake: float) -> None:
        self.total_exposure += stake
        for market_id in opportunity.market_ids:
            self.market_exposure[market_id] = self.market_exposure.get(market_id, 0.0) + stake


def decide_trade(opportunity: Opportunity, cfg: BotConfig, mode: str, guard: RiskGuard) -> TradeDecision:
    qualifies = opportunity.qualifies_for_paper if mode == "paper" else opportunity.qualifies_for_live
    stake = cfg.paper_stake if mode == "paper" else cfg.live_stake
    if not qualifies:
        return TradeDecision(opportunity.opportunity_id, mode, False, "does not pass quality thresholds", opportunity.net_edge, stake)
    ok, reason = guard.can_trade(opportunity, stake, mode)
    if not ok:
        return TradeDecision(opportunity.opportunity_id, mode, False, reason, opportunity.net_edge, stake)
    return TradeDecision(opportunity.opportunity_id, mode, True, "trade approved", opportunity.net_edge, stake)
