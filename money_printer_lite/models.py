from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Asset = Literal["BTC", "ETH"]
RelationshipType = Literal["monotonicity", "bucket", "complement"]
OpportunityClass = Literal["true_arbitrage", "near_arbitrage", "mispricing"]
BotMode = Literal["paper", "live"]


@dataclass(slots=True)
class Market:
    market_id: str
    slug: str
    question: str
    asset: Asset
    expiry: str
    threshold: float | None
    range_low: float | None
    range_high: float | None
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    volume: float
    liquidity_hint: float
    updated_at: datetime


@dataclass(slots=True)
class MarketGroup:
    group_id: str
    asset: Asset
    expiry: str
    markets: list[Market] = field(default_factory=list)


@dataclass(slots=True)
class Opportunity:
    opportunity_id: str
    detected_at: datetime
    relationship_type: RelationshipType
    opportunity_class: OpportunityClass
    asset: Asset
    group_id: str
    market_ids: list[str]
    description: str
    gross_edge: float
    estimated_fees: float
    estimated_slippage: float
    estimated_fill_quality: float
    order_book_depth: float
    net_edge: float
    max_theoretical_profit: float
    max_theoretical_loss: float
    confidence_score: float
    qualifies_for_paper: bool
    qualifies_for_live: bool


@dataclass(slots=True)
class TradeDecision:
    opportunity_id: str
    mode: BotMode
    taken: bool
    reason: str
    expected_edge: float
    stake: float


@dataclass(slots=True)
class ExecutedTrade:
    trade_id: str
    opportunity_id: str
    mode: BotMode
    asset: Asset
    setup_type: RelationshipType
    market_ids: list[str]
    stake: float
    expected_edge: float
    realized_pnl: float
    fill_ratio: float
    opened_at: datetime
    closed_at: datetime
