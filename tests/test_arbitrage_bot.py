import unittest

from arbitrage_bot import Opportunity, VenueQuote, detect_opportunities, normalize_market_title, render_opportunities, title_similarity


class ArbitrageBotTests(unittest.TestCase):
    def test_normalize_market_title_removes_noise(self):
        self.assertEqual(
            normalize_market_title("Will Bitcoin close above $100k on Dec. 31?"),
            "bitcoin close above 100k dec 31",
        )

    def test_title_similarity_prefers_same_question(self):
        similar = title_similarity(
            "Will BTC close above 100k on Dec 31?",
            "Bitcoin above $100k by December 31?",
        )
        different = title_similarity(
            "Will BTC close above 100k on Dec 31?",
            "Will the Fed cut rates next meeting?",
        )
        self.assertGreater(similar, different)
        self.assertGreater(similar, 0.55)

    def test_detect_opportunities_finds_cross_market_edge(self):
        poly = VenueQuote(
            venue="Polymarket",
            market_id="poly-1",
            title="Will Bitcoin close above $100k on Dec 31?",
            url="https://polymarket.com/event/btc-100k",
            yes_bid=0.57,
            yes_ask=0.60,
            no_bid=0.40,
            no_ask=0.43,
            last_price=0.59,
        )
        kalshi = VenueQuote(
            venue="Kalshi",
            market_id="KXBTC100K-24DEC31-T100",
            title="Bitcoin above $100k by December 31?",
            url="https://kalshi.com/markets/KXBTC100K-24DEC31-T100",
            yes_bid=0.44,
            yes_ask=0.62,
            no_bid=0.53,
            no_ask=0.36,
            last_price=0.45,
        )

        opportunities = detect_opportunities([poly], [kalshi], min_similarity=0.55, min_edge=0.02)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(
            opportunities[0].strategy,
            "Buy YES on Polymarket + Buy NO on Kalshi",
        )
        self.assertAlmostEqual(opportunities[0].locked_in_edge, 0.04)

    def test_render_opportunities_includes_urls(self):
        poly = VenueQuote(
            venue="Polymarket",
            market_id="poly-1",
            title="Will ETH close above $5k on Dec 31?",
            url="https://polymarket.com/event/eth-5k",
            yes_bid=0.30,
            yes_ask=0.31,
            no_bid=0.69,
            no_ask=0.70,
            last_price=0.305,
        )
        kalshi = VenueQuote(
            venue="Kalshi",
            market_id="KXETH5K-24DEC31-T5000",
            title="ETH above $5k by December 31?",
            url="https://kalshi.com/markets/KXETH5K-24DEC31-T5000",
            yes_bid=0.20,
            yes_ask=0.21,
            no_bid=0.78,
            no_ask=0.68,
            last_price=0.205,
        )
        opportunity = Opportunity(
            polymarket=poly,
            kalshi=kalshi,
            strategy="Buy YES on Polymarket + Buy NO on Kalshi",
            total_cost=0.99,
            locked_in_edge=0.01,
            title_similarity=0.8,
            price_dislocation=0.1,
        )

        rendered = render_opportunities([opportunity], limit=5)

        self.assertIn("https://polymarket.com/event/eth-5k", rendered)
        self.assertIn("https://kalshi.com/markets/KXETH5K-24DEC31-T5000", rendered)
        self.assertIn("Locked-in edge", rendered)


if __name__ == "__main__":
    unittest.main()
