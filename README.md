# Cross Arbitrage Bot

This repository contains a **display-only** command-line bot that looks for binary market price mismatches between **Polymarket** and **Kalshi**. It does **not** place orders or automate trading.

## What it does

- fetches active markets from Polymarket and open markets from Kalshi
- normalizes market titles and matches the closest cross-venue questions
- checks for synthetic arbitrage using two-leg binary combinations:
  - buy **YES** on Polymarket + buy **NO** on Kalshi
  - buy **NO** on Polymarket + buy **YES** on Kalshi
- prints only the opportunities whose combined cost is below 100% by your chosen threshold

## Quick start

```bash
python arbitrage_bot.py --limit 10 --markets-per-venue 200 --min-edge 0.02
```

## Options

- `--limit`: maximum number of opportunities to print
- `--markets-per-venue`: number of markets fetched from each venue
- `--min-similarity`: minimum fuzzy-title match score required before comparing markets
- `--min-edge`: minimum locked-in edge required before displaying a result

## Notes and caveats

- Matching is heuristic and based on question similarity; review every flagged market manually.
- Venue APIs can change field names over time, so parsing code includes a few fallback keys.
- Network restrictions or anti-bot controls may block API calls in some environments.
- This tool is informational only and intentionally does not submit or stage orders.
