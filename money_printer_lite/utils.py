from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

ASSET_RE = re.compile(r"\b(bitcoin|btc|ethereum|eth)\b", re.I)
THRESHOLD_RE = re.compile(r"\b(?:above|over|below|under)\s*\$?([0-9]{2,3}(?:,[0-9]{3})*(?:k|m)?)", re.I)
RANGE_RE = re.compile(r"\b(?:between|from)\s*\$?([0-9]{2,3}(?:,[0-9]{3})*(?:k|m)?)\s*(?:and|to|-|–)\s*\$?([0-9]{2,3}(?:,[0-9]{3})*(?:k|m)?)", re.I)
DATE_RE = re.compile(r"\b(by|on)\s+([a-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)", re.I)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_price_token(token: str) -> float:
    t = token.lower().replace(",", "").strip()
    multiplier = 1.0
    if t.endswith("k"):
        multiplier = 1000.0
        t = t[:-1]
    elif t.endswith("m"):
        multiplier = 1_000_000.0
        t = t[:-1]
    return float(t) * multiplier


def normalize_expiry(question: str) -> str:
    m = DATE_RE.search(question)
    if not m:
        return "unknown"
    return m.group(2).lower().replace("  ", " ").strip()
