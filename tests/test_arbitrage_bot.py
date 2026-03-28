import unittest
from unittest.mock import patch

from cross_arbitrage.core import compare_titles, detect_opportunities, render_opportunities_text
from cross_arbitrage.dashboard import build_dashboard_html
from cross_arbitrage.data import FixtureKalshiClient, FixturePolymarketClient, run_scan


class ArbitrageBotTests(unittest.TestCase):
    def test_strict_matching_accepts_same_market(self):
        diagnostics = compare_titles(
            "Will Bitcoin close above $100k on Dec 31?",
            "Bitcoin above $100k by December 31?",
        )
        self.assertGreaterEqual(diagnostics.score, 0.72)
        self.assertIn("100k", diagnostics.shared_numbers)

    def test_strict_matching_rejects_number_mismatch(self):
        diagnostics = compare_titles(
            "Will Bitcoin close above $100k on Dec 31?",
            "Bitcoin above $90k by December 31?",
        )
        self.assertEqual(diagnostics.score, 0.0)
        self.assertEqual(diagnostics.reason, "numeric tokens do not align")

    def test_strict_matching_rejects_direction_mismatch(self):
        diagnostics = compare_titles(
            "Will ETH close above $5k on Dec 31?",
            "Ethereum below $5k by December 31?",
        )
        self.assertEqual(diagnostics.score, 0.0)
        self.assertEqual(diagnostics.reason, "directional terms conflict")

    def test_fixture_scan_finds_one_opportunity(self):
        result = run_scan(mode="mock", markets_per_venue=20, min_similarity=0.72, min_edge=0.02)
        self.assertEqual(result.source_mode, "mock")
        self.assertEqual(result.polymarket_count, 3)
        self.assertEqual(result.kalshi_count, 3)
        self.assertEqual(len(result.opportunities), 1)
        self.assertIn("Bitcoin", result.opportunities[0].polymarket.title)

    def test_auto_mode_falls_back_to_fixtures(self):
        with patch("cross_arbitrage.data.LivePolymarketClient.fetch_markets", side_effect=RuntimeError("network down")):
            result = run_scan(mode="auto", markets_per_venue=20, min_similarity=0.72, min_edge=0.02)
        self.assertEqual(result.source_mode, "mock-fallback")
        self.assertIsNotNone(result.warning)
        self.assertEqual(len(result.opportunities), 1)

    def test_render_text_includes_source_mode(self):
        result = run_scan(mode="mock", markets_per_venue=20, min_similarity=0.72, min_edge=0.02)
        rendered = render_opportunities_text(result, limit=5)
        self.assertIn("Source mode: mock", rendered)
        self.assertIn("Shared tokens", rendered)
        self.assertIn("https://polymarket.com/event/bitcoin-above-100k-dec-31", rendered)

    def test_dashboard_html_contains_summary_cards(self):
        result = run_scan(mode="mock", markets_per_venue=20, min_similarity=0.72, min_edge=0.02)
        html = build_dashboard_html(result, limit=5, refresh_seconds=30)
        self.assertIn("Cross Arbitrage Dashboard", html)
        self.assertIn("Source mode: mock", html)
        self.assertIn("Displayed opportunities", html)
        self.assertIn("Polymarket", html)
        self.assertIn("Kalshi", html)

    def test_fixture_clients_load_expected_counts(self):
        self.assertEqual(len(FixturePolymarketClient().fetch_markets(10)), 3)
        self.assertEqual(len(FixtureKalshiClient().fetch_markets(10)), 3)

    def test_detect_opportunities_filters_unrelated_market(self):
        poly_quotes = FixturePolymarketClient().fetch_markets(10)
        kalshi_quotes = FixtureKalshiClient().fetch_markets(10)
        opportunities = detect_opportunities(poly_quotes, kalshi_quotes, min_similarity=0.72, min_edge=0.02)
        titles = [item.polymarket.title for item in opportunities]
        self.assertNotIn("Will the Fed cut rates at the next meeting?", titles)


if __name__ == "__main__":
    unittest.main()
