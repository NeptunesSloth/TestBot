import json
import os
import tempfile
import unittest

from money_printer_lite.arbitrage_engine import detect_opportunities
from money_printer_lite.bot import create_runtime, run_cycle
from money_printer_lite.config import BotConfig
from money_printer_lite.market_discovery import discover_crypto_markets
from money_printer_lite.relationship_builder import build_groups


class MoneyPrinterLiteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = "fixtures/polymarket_crypto_sample.json"

    def test_discovery_filters_to_crypto(self):
        with open(self.fixture, "r", encoding="utf-8") as fh:
            raw = json.loads(fh.read())
        markets = discover_crypto_markets(raw)
        self.assertEqual(len(markets), 5)
        self.assertEqual({m.asset for m in markets}, {"BTC", "ETH"})

    def test_grouping_by_asset_and_expiry(self):
        with open(self.fixture, "r", encoding="utf-8") as fh:
            raw = json.loads(fh.read())
        groups = build_groups(discover_crypto_markets(raw))
        self.assertEqual(len(groups), 2)
        ids = {g.group_id for g in groups}
        self.assertTrue(any(g.startswith("BTC-") for g in ids))

    def test_opportunity_detection_and_scoring(self):
        with open(self.fixture, "r", encoding="utf-8") as fh:
            raw = json.loads(fh.read())
        markets = discover_crypto_markets(raw)
        groups = build_groups(markets)
        cfg = BotConfig(min_net_edge=0.01)
        opportunities = detect_opportunities(groups, cfg)
        self.assertGreaterEqual(len(opportunities), 1)
        self.assertTrue(any(o.relationship_type == "monotonicity" for o in opportunities))
        self.assertTrue(any(o.net_edge != 0 for o in opportunities))

    def test_run_cycle_stores_results_and_trades(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            cfg = BotConfig(db_path=db_path, bot_mode="paper", min_net_edge=0.005)
            storage, client, guard = create_runtime(cfg, fixture_path=self.fixture)
            summary = run_cycle(cfg, storage, client, guard)
            self.assertGreater(summary["markets"], 0)
            self.assertGreater(summary["opportunities"], 0)
            metrics = storage.dashboard_metrics()
            self.assertIn("total_hypothetical_pnl", metrics)


if __name__ == "__main__":
    unittest.main()
