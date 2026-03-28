from __future__ import annotations

import argparse

from money_printer_lite.bot import create_runtime, run_cycle
from money_printer_lite.config import BotConfig
from money_printer_lite.dashboard import serve_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket-only crypto arbitrage money-printer-lite bot")
    parser.add_argument("--fixture", help="optional fixture path for Polymarket markets JSON")
    parser.add_argument("--run-once", action="store_true", help="run one scan/trade cycle and exit")
    parser.add_argument("--dashboard", action="store_true", help="start Flask dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = BotConfig.from_env()
    storage, client, guard = create_runtime(cfg, fixture_path=args.fixture)

    summary = run_cycle(cfg, storage, client, guard)
    print(summary)

    if args.dashboard:
        serve_dashboard(storage, host=args.host, port=args.port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
