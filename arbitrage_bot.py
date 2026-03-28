from __future__ import annotations

import argparse
import sys

from cross_arbitrage import render_opportunities_text, run_scan, serve_dashboard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Display cross-exchange arbitrage opportunities between Polymarket and Kalshi.",
    )
    parser.add_argument("--limit", type=int, default=10, help="maximum opportunities to display")
    parser.add_argument(
        "--markets-per-venue",
        type=int,
        default=200,
        help="how many active/open markets to fetch from each venue",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.72,
        help="minimum strict title similarity required to match markets",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.02,
        help="minimum locked-in edge required before displaying a result",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "live", "mock"),
        default="auto",
        help="data source mode: live APIs, bundled fixtures, or auto fallback to fixtures",
    )
    parser.add_argument("--polymarket-fixture", help="optional path to a Polymarket fixture JSON file")
    parser.add_argument("--kalshi-fixture", help="optional path to a Kalshi fixture JSON file")
    parser.add_argument("--serve", action="store_true", help="run a lightweight local dashboard instead of printing text")
    parser.add_argument("--host", default="127.0.0.1", help="dashboard bind host")
    parser.add_argument("--port", type=int, default=8000, help="dashboard bind port")
    parser.add_argument("--refresh-seconds", type=int, default=30, help="dashboard auto-refresh interval")
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.limit <= 0 or args.markets_per_venue <= 0:
        parser.error("--limit and --markets-per-venue must be positive integers")
    if not (0 <= args.min_similarity <= 1):
        parser.error("--min-similarity must be between 0 and 1")
    if not (0 <= args.min_edge <= 1):
        parser.error("--min-edge must be between 0 and 1")
    if args.port <= 0 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.refresh_seconds <= 0:
        parser.error("--refresh-seconds must be positive")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    def result_factory():
        return run_scan(
            mode=args.mode,
            markets_per_venue=args.markets_per_venue,
            min_similarity=args.min_similarity,
            min_edge=args.min_edge,
            polymarket_fixture=args.polymarket_fixture,
            kalshi_fixture=args.kalshi_fixture,
        )

    if args.serve:
        serve_dashboard(
            result_factory=result_factory,
            host=args.host,
            port=args.port,
            limit=args.limit,
            refresh_seconds=args.refresh_seconds,
        )
        return 0

    result = result_factory()
    if result.error:
        print(result.error, file=sys.stderr)
        return 1
    print(render_opportunities_text(result, limit=args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
