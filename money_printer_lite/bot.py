from __future__ import annotations

import logging

from money_printer_lite.alerts import alert_high_confidence, alert_new_opportunity, alert_stale_data
from money_printer_lite.arbitrage_engine import detect_opportunities
from money_printer_lite.clients.polymarket_client import PolymarketClient
from money_printer_lite.config import BotConfig
from money_printer_lite.execution import RiskGuard, decide_trade
from money_printer_lite.live_trader import LiveOrderExecutor
from money_printer_lite.market_discovery import discover_crypto_markets
from money_printer_lite.paper_trader import execute_paper_trade
from money_printer_lite.relationship_builder import build_groups
from money_printer_lite.storage import SQLiteStorage
from money_printer_lite.utils import configure_logging, utcnow


logger = logging.getLogger("money_printer_lite")


def run_cycle(cfg: BotConfig, storage: SQLiteStorage, client: PolymarketClient, guard: RiskGuard) -> dict:
    now = utcnow()
    raw = client.fetch_markets(limit=250)
    markets = discover_crypto_markets(raw)
    if not markets:
        alert_stale_data(cfg.stale_data_seconds)
        storage.health_event("WARN", "stale_data", "No crypto markets discovered", now.isoformat())

    groups = build_groups(markets)
    opportunities = detect_opportunities(groups, cfg)

    storage.upsert_markets(markets)
    storage.upsert_groups(groups, now.isoformat())
    storage.insert_opportunities(opportunities)

    mode = "live" if cfg.bot_mode == "live" else "paper"
    live_exec = LiveOrderExecutor(enabled=cfg.live_trading)

    trades_taken = 0
    for opp in opportunities[:15]:
        alert_new_opportunity(opp)
        if opp.confidence_score >= cfg.high_confidence_threshold:
            alert_high_confidence(opp)

        decision = decide_trade(opp, cfg, mode, guard)
        if not decision.taken:
            continue

        if mode == "paper":
            trade = execute_paper_trade(opp, decision.stake, cfg.min_depth)
        else:
            try:
                trade = live_exec.place_orders(opp, decision.stake)
            except Exception as exc:
                storage.error_event("live_trader", str(exc), utcnow().isoformat())
                continue

        storage.insert_trade(trade)
        guard.register_trade(opp, trade.stake)
        trades_taken += 1

    storage.snapshot(mode, now.isoformat())
    return {
        "markets": len(markets),
        "groups": len(groups),
        "opportunities": len(opportunities),
        "trades_taken": trades_taken,
    }


def create_runtime(cfg: BotConfig, fixture_path: str | None = None) -> tuple[SQLiteStorage, PolymarketClient, RiskGuard]:
    configure_logging()
    storage = SQLiteStorage(cfg.db_path)
    storage.init()
    client = PolymarketClient(fixture_path=fixture_path)
    guard = RiskGuard(cfg)
    return storage, client, guard
