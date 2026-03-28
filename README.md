# Polymarket Money Printer Lite (BTC/ETH only)

A conservative, **Polymarket-only** crypto arbitrage/mispricing bot focused on the cleanest opportunities in BTC/ETH price markets.

It is intentionally selective: fewer trades, higher-quality setups, and net-edge filtering after fee/slippage assumptions.

## What this bot does

1. Discovers Polymarket BTC/ETH price markets.
2. Groups related contracts by `(asset, expiry)`.
3. Detects clean relationship violations:
   - Monotonicity violations in threshold markets.
   - Mutually exclusive bucket sum mispricing.
   - Near-complement divergence checks.
4. Scores each setup for **net edge** using fee/slippage/fill quality/depth.
5. Trades only opportunities above configurable quality thresholds.
6. Supports paper mode and safety-gated live mode.
7. Stores opportunities/trades/health events in SQLite.
8. Shows local dashboard + JSON APIs.

## True arbitrage vs mispricing

### True arbitrage (strictly bounded payoff)
- Relationship is logically bounded (e.g., monotonic threshold ordering or complete disjoint bucket sums).
- Opportunity survives fee + slippage assumptions.

### Mispricing / near-arbitrage
- Relationship is plausible but not perfectly bounded (e.g., near-complements).
- Useful signal, but treated with lower confidence and stricter live gating.

## Paper mode P&L model

Paper mode simulates:
- realistic fill ratio from available depth,
- partial fills when depth is weak,
- conservative realization fraction of expected edge.

Stored metrics allow comparing:
- opportunity seen vs trade taken,
- expected edge at entry vs realized P&L,
- setup type and asset-level outcomes.

## Live mode safety

Live mode is disabled by default.

To enable:
1. `BOT_MODE=live`
2. `LIVE_TRADING=true`
3. keep small `LIVE_STAKE` and conservative caps.

Safety checks include:
- kill switch,
- max position size,
- per-market and total exposure caps,
- high-confidence and depth thresholds,
- API error handling and retry backoff,
- no fill assumptions without explicit execution result.

## Run

```bash
python -m money_printer_lite.main --fixture fixtures/polymarket_crypto_sample.json --run-once
```

Start dashboard:

```bash
python -m money_printer_lite.main --fixture fixtures/polymarket_crypto_sample.json --dashboard --host 127.0.0.1 --port 5000
```

## Dashboard sections included

- Overview cards (P&L, exposure, opportunities, trades, average edge, win/loss)
- Active opportunities
- Paper trade history
- Live trade history
- JSON endpoints for integration

## SQLite tables

- markets
- grouped_market_sets
- opportunities
- paper_trades
- live_trades
- fills
- pnl_snapshots
- bot_health_events
- errors_log_summaries

## Known limitations / failure cases

- Live order placement uses a conservative integration stub unless you wire authenticated Polymarket order APIs.
- Some contract relationships require richer metadata than question parsing alone.
- Bucket completeness is inferred only from discovered markets; missing buckets can cause false negatives.
- Fee/slippage assumptions are configurable estimates, not guarantees.

## Design philosophy

- prioritize net profitability over activity,
- skip low-quality setups,
- avoid overtrading,
- simple and inspectable logic,
- no ML, no extra exchanges, no black box.
