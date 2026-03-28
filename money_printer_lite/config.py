from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class BotConfig:
    bot_mode: str = "paper"
    live_trading: bool = False
    kill_switch: bool = False
    min_net_edge: float = 0.015
    min_depth: float = 1500.0
    fee_rate: float = 0.01
    slippage_bps: float = 30.0
    paper_stake: float = 25.0
    live_stake: float = 5.0
    max_position_size: float = 40.0
    per_market_exposure_cap: float = 60.0
    total_exposure_cap: float = 200.0
    cooldown_seconds: int = 300
    high_confidence_threshold: float = 0.82
    db_path: str = "bot.db"
    poll_interval_seconds: int = 60
    stale_data_seconds: int = 180

    @staticmethod
    def from_env() -> "BotConfig":
        def get_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        def get_float(name: str, default: float) -> float:
            raw = os.getenv(name)
            return default if raw is None else float(raw)

        def get_int(name: str, default: int) -> int:
            raw = os.getenv(name)
            return default if raw is None else int(raw)

        return BotConfig(
            bot_mode=os.getenv("BOT_MODE", "paper").lower(),
            live_trading=get_bool("LIVE_TRADING", False),
            kill_switch=get_bool("KILL_SWITCH", False),
            min_net_edge=get_float("MIN_NET_EDGE", 0.015),
            min_depth=get_float("MIN_DEPTH", 1500.0),
            fee_rate=get_float("FEE_RATE", 0.01),
            slippage_bps=get_float("SLIPPAGE_BPS", 30.0),
            paper_stake=get_float("PAPER_STAKE", 25.0),
            live_stake=get_float("LIVE_STAKE", 5.0),
            max_position_size=get_float("MAX_POSITION_SIZE", 40.0),
            per_market_exposure_cap=get_float("PER_MARKET_EXPOSURE_CAP", 60.0),
            total_exposure_cap=get_float("TOTAL_EXPOSURE_CAP", 200.0),
            cooldown_seconds=get_int("COOLDOWN_SECONDS", 300),
            high_confidence_threshold=get_float("HIGH_CONFIDENCE_THRESHOLD", 0.82),
            db_path=os.getenv("DB_PATH", "bot.db"),
            poll_interval_seconds=get_int("POLL_INTERVAL_SECONDS", 60),
            stale_data_seconds=get_int("STALE_DATA_SECONDS", 180),
        )
