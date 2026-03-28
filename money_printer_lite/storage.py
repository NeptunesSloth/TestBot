from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from money_printer_lite.models import ExecutedTrade, Market, MarketGroup, Opportunity


SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
  market_id TEXT PRIMARY KEY,
  asset TEXT NOT NULL,
  expiry TEXT NOT NULL,
  question TEXT NOT NULL,
  yes_bid REAL NOT NULL,
  yes_ask REAL NOT NULL,
  no_bid REAL NOT NULL,
  no_ask REAL NOT NULL,
  volume REAL NOT NULL,
  liquidity_hint REAL NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grouped_market_sets (
  group_id TEXT PRIMARY KEY,
  asset TEXT NOT NULL,
  expiry TEXT NOT NULL,
  market_count INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
  opportunity_id TEXT PRIMARY KEY,
  detected_at TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  opportunity_class TEXT NOT NULL,
  asset TEXT NOT NULL,
  group_id TEXT NOT NULL,
  market_ids TEXT NOT NULL,
  description TEXT NOT NULL,
  gross_edge REAL NOT NULL,
  estimated_fees REAL NOT NULL,
  estimated_slippage REAL NOT NULL,
  estimated_fill_quality REAL NOT NULL,
  order_book_depth REAL NOT NULL,
  net_edge REAL NOT NULL,
  max_theoretical_profit REAL NOT NULL,
  max_theoretical_loss REAL NOT NULL,
  confidence_score REAL NOT NULL,
  qualifies_for_paper INTEGER NOT NULL,
  qualifies_for_live INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_trades (
  trade_id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  asset TEXT NOT NULL,
  setup_type TEXT NOT NULL,
  market_ids TEXT NOT NULL,
  stake REAL NOT NULL,
  expected_edge REAL NOT NULL,
  realized_pnl REAL NOT NULL,
  fill_ratio REAL NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS live_trades (
  trade_id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  asset TEXT NOT NULL,
  setup_type TEXT NOT NULL,
  market_ids TEXT NOT NULL,
  stake REAL NOT NULL,
  expected_edge REAL NOT NULL,
  realized_pnl REAL NOT NULL,
  fill_ratio REAL NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fills (
  fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id TEXT NOT NULL,
  market_id TEXT NOT NULL,
  side TEXT NOT NULL,
  price REAL NOT NULL,
  size REAL NOT NULL,
  filled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pnl_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  total_pnl REAL NOT NULL,
  open_exposure REAL NOT NULL,
  opportunities_today INTEGER NOT NULL,
  trades_today INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bot_health_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  level TEXT NOT NULL,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS errors_log_summaries (
  error_id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  module TEXT NOT NULL,
  message TEXT NOT NULL
);
"""


class SQLiteStorage:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_markets(self, markets: list[Market]) -> None:
        self.conn.executemany(
            """
            INSERT INTO markets (market_id, asset, expiry, question, yes_bid, yes_ask, no_bid, no_ask, volume, liquidity_hint, updated_at)
            VALUES (:market_id, :asset, :expiry, :question, :yes_bid, :yes_ask, :no_bid, :no_ask, :volume, :liquidity_hint, :updated_at)
            ON CONFLICT(market_id) DO UPDATE SET
              yes_bid=excluded.yes_bid,
              yes_ask=excluded.yes_ask,
              no_bid=excluded.no_bid,
              no_ask=excluded.no_ask,
              volume=excluded.volume,
              liquidity_hint=excluded.liquidity_hint,
              updated_at=excluded.updated_at
            """,
            [
                {
                    "market_id": m.market_id,
                    "asset": m.asset,
                    "expiry": m.expiry,
                    "question": m.question,
                    "yes_bid": m.yes_bid,
                    "yes_ask": m.yes_ask,
                    "no_bid": m.no_bid,
                    "no_ask": m.no_ask,
                    "volume": m.volume,
                    "liquidity_hint": m.liquidity_hint,
                    "updated_at": m.updated_at.isoformat(),
                }
                for m in markets
            ],
        )
        self.conn.commit()

    def upsert_groups(self, groups: list[MarketGroup], ts: str) -> None:
        self.conn.executemany(
            """
            INSERT INTO grouped_market_sets(group_id, asset, expiry, market_count, updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(group_id) DO UPDATE SET market_count=excluded.market_count, updated_at=excluded.updated_at
            """,
            [(g.group_id, g.asset, g.expiry, len(g.markets), ts) for g in groups],
        )
        self.conn.commit()

    def insert_opportunities(self, opportunities: list[Opportunity]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO opportunities(
              opportunity_id, detected_at, relationship_type, opportunity_class, asset, group_id, market_ids, description,
              gross_edge, estimated_fees, estimated_slippage, estimated_fill_quality, order_book_depth, net_edge,
              max_theoretical_profit, max_theoretical_loss, confidence_score, qualifies_for_paper, qualifies_for_live
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    o.opportunity_id,
                    o.detected_at.isoformat(),
                    o.relationship_type,
                    o.opportunity_class,
                    o.asset,
                    o.group_id,
                    json.dumps(o.market_ids),
                    o.description,
                    o.gross_edge,
                    o.estimated_fees,
                    o.estimated_slippage,
                    o.estimated_fill_quality,
                    o.order_book_depth,
                    o.net_edge,
                    o.max_theoretical_profit,
                    o.max_theoretical_loss,
                    o.confidence_score,
                    int(o.qualifies_for_paper),
                    int(o.qualifies_for_live),
                )
                for o in opportunities
            ],
        )
        self.conn.commit()

    def insert_trade(self, trade: ExecutedTrade) -> None:
        table = "paper_trades" if trade.mode == "paper" else "live_trades"
        self.conn.execute(
            f"""
            INSERT INTO {table}(trade_id, opportunity_id, asset, setup_type, market_ids, stake, expected_edge, realized_pnl, fill_ratio, opened_at, closed_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                trade.trade_id,
                trade.opportunity_id,
                trade.asset,
                trade.setup_type,
                json.dumps(trade.market_ids),
                trade.stake,
                trade.expected_edge,
                trade.realized_pnl,
                trade.fill_ratio,
                trade.opened_at.isoformat(),
                trade.closed_at.isoformat(),
            ),
        )
        self.conn.commit()

    def health_event(self, level: str, event_type: str, message: str, ts: str) -> None:
        self.conn.execute(
            "INSERT INTO bot_health_events(timestamp, level, event_type, message) VALUES(?,?,?,?)",
            (ts, level, event_type, message),
        )
        self.conn.commit()

    def error_event(self, module: str, message: str, ts: str) -> None:
        self.conn.execute(
            "INSERT INTO errors_log_summaries(timestamp, module, message) VALUES(?,?,?)",
            (ts, module, message),
        )
        self.conn.commit()

    def snapshot(self, mode: str, ts: str) -> None:
        total_pnl = self.conn.execute("SELECT COALESCE(SUM(realized_pnl),0) FROM paper_trades").fetchone()[0]
        if mode == "live":
            total_pnl += self.conn.execute("SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades").fetchone()[0]
        trades_today = self.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE date(closed_at)=date('now')"
        ).fetchone()[0]
        opportunities_today = self.conn.execute(
            "SELECT COUNT(*) FROM opportunities WHERE date(detected_at)=date('now')"
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO pnl_snapshots(mode, timestamp, total_pnl, open_exposure, opportunities_today, trades_today) VALUES(?,?,?,?,?,?)",
            (mode, ts, float(total_pnl), 0.0, int(opportunities_today), int(trades_today)),
        )
        self.conn.commit()

    def dashboard_metrics(self) -> dict:
        q = self.conn
        best = q.execute(
            "SELECT setup_type, COALESCE(SUM(realized_pnl),0) pnl FROM paper_trades GROUP BY setup_type ORDER BY pnl DESC LIMIT 1"
        ).fetchone()
        worst = q.execute(
            "SELECT setup_type, COALESCE(SUM(realized_pnl),0) pnl FROM paper_trades GROUP BY setup_type ORDER BY pnl ASC LIMIT 1"
        ).fetchone()
        return {
            "total_hypothetical_pnl": q.execute("SELECT COALESCE(SUM(realized_pnl),0) FROM paper_trades").fetchone()[0],
            "realized_pnl": q.execute("SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades").fetchone()[0],
            "open_exposure": 0.0,
            "opportunities_today": q.execute("SELECT COUNT(*) FROM opportunities WHERE date(detected_at)=date('now')").fetchone()[0],
            "trades_today": q.execute("SELECT COUNT(*) FROM paper_trades WHERE date(closed_at)=date('now')").fetchone()[0]
            + q.execute("SELECT COUNT(*) FROM live_trades WHERE date(closed_at)=date('now')").fetchone()[0],
            "average_net_edge": q.execute("SELECT COALESCE(AVG(net_edge),0) FROM opportunities").fetchone()[0],
            "best_setup": (dict(best) if best else None),
            "worst_setup": (dict(worst) if worst else None),
            "win_count": q.execute("SELECT COUNT(*) FROM paper_trades WHERE realized_pnl > 0").fetchone()[0],
            "loss_count": q.execute("SELECT COUNT(*) FROM paper_trades WHERE realized_pnl <= 0").fetchone()[0],
        }

    def latest_opportunities(self, limit: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM opportunities ORDER BY detected_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def trades(self, mode: str, limit: int = 50) -> list[dict]:
        table = "paper_trades" if mode == "paper" else "live_trades"
        rows = self.conn.execute(f"SELECT * FROM {table} ORDER BY closed_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
