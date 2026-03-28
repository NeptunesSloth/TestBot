from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "will",
    "with",
}

TOKEN_ALIASES = {
    "btc": "bitcoin",
    "xbt": "bitcoin",
    "eth": "ethereum",
    "dems": "democrat",
    "dem": "democrat",
    "gop": "republican",
    "rep": "republican",
    "reps": "republican",
    "december": "dec",
    "january": "jan",
    "february": "feb",
    "march": "mar",
    "april": "apr",
    "june": "jun",
    "july": "jul",
    "august": "aug",
    "september": "sep",
    "october": "oct",
    "november": "nov",
    "greater": "above",
    "over": "above",
    "higher": "above",
    "hike": "above",
    "raise": "above",
    "less": "below",
    "lower": "below",
    "under": "below",
    "cut": "below",
}
NUMERIC_RE = re.compile(r"[a-z0-9]+")
ABOVE_TOKENS = {"above"}
BELOW_TOKENS = {"below"}
DATE_TOKENS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}


@dataclass(frozen=True)
class VenueQuote:
    venue: str
    market_id: str
    title: str
    url: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    last_price: float | None
    volume: float | None = None
    close_time: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def mid_price(self) -> float | None:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2
        return self.last_price


@dataclass(frozen=True)
class MatchDiagnostics:
    score: float
    sequence_score: float
    token_jaccard: float
    numeric_score: float
    shared_tokens: tuple[str, ...]
    shared_numbers: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Opportunity:
    polymarket: VenueQuote
    kalshi: VenueQuote
    strategy: str
    total_cost: float
    locked_in_edge: float
    price_dislocation: float | None
    diagnostics: MatchDiagnostics


@dataclass(frozen=True)
class ScanResult:
    opportunities: list[Opportunity]
    polymarket_count: int
    kalshi_count: int
    source_mode: str
    warning: str | None = None
    error: str | None = None


def normalize_token(token: str) -> str:
    return TOKEN_ALIASES.get(token, token)


def normalize_market_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower())
    tokens = [normalize_token(tok) for tok in NUMERIC_RE.findall(cleaned)]
    return " ".join(tok for tok in tokens if tok not in STOP_WORDS)


def tokenize_title(title: str) -> list[str]:
    return normalize_market_title(title).split()


def extract_numeric_tokens(tokens: Iterable[str]) -> set[str]:
    return {tok for tok in tokens if any(ch.isdigit() for ch in tok) or tok in DATE_TOKENS}


def extract_price_tokens(tokens: Iterable[str]) -> set[str]:
    return {tok for tok in tokens if any(ch.isdigit() for ch in tok) and tok not in DATE_TOKENS}


def extract_direction(tokens: Iterable[str]) -> str | None:
    token_set = set(tokens)
    if token_set & ABOVE_TOKENS:
        return "above"
    if token_set & BELOW_TOKENS:
        return "below"
    return None


def compare_titles(left: str, right: str) -> MatchDiagnostics:
    left_tokens = tokenize_title(left)
    right_tokens = tokenize_title(right)
    left_set = set(left_tokens)
    right_set = set(right_tokens)

    if not left_set or not right_set:
        return MatchDiagnostics(0.0, 0.0, 0.0, 0.0, (), (), "missing title tokens")

    left_numbers = extract_numeric_tokens(left_tokens)
    right_numbers = extract_numeric_tokens(right_tokens)
    shared_numbers = tuple(sorted(left_numbers & right_numbers))
    left_prices = extract_price_tokens(left_tokens)
    right_prices = extract_price_tokens(right_tokens)
    if left_prices and right_prices and left_prices != right_prices:
        return MatchDiagnostics(0.0, 0.0, 0.0, 0.0, (), shared_numbers, "numeric tokens do not align")
    if left_numbers and right_numbers and not shared_numbers:
        return MatchDiagnostics(0.0, 0.0, 0.0, 0.0, (), (), "numeric tokens do not align")

    left_direction = extract_direction(left_tokens)
    right_direction = extract_direction(right_tokens)
    if left_direction and right_direction and left_direction != right_direction:
        return MatchDiagnostics(0.0, 0.0, 0.0, 0.0, (), shared_numbers, "directional terms conflict")

    shared_tokens = tuple(sorted((left_set & right_set) - STOP_WORDS))
    if len(shared_tokens) < 2:
        return MatchDiagnostics(0.0, 0.0, 0.0, 0.0, shared_tokens, shared_numbers, "not enough shared semantic tokens")

    sequence_score = SequenceMatcher(a=" ".join(left_tokens), b=" ".join(right_tokens)).ratio()
    token_jaccard = len(left_set & right_set) / len(left_set | right_set)
    if left_numbers or right_numbers:
        numeric_score = len(left_numbers & right_numbers) / len(left_numbers | right_numbers)
    else:
        numeric_score = 1.0

    score = (0.45 * token_jaccard) + (0.35 * sequence_score) + (0.20 * numeric_score)
    reason = "strong title alignment" if score >= 0.75 else "candidate title alignment"
    return MatchDiagnostics(score, sequence_score, token_jaccard, numeric_score, shared_tokens, shared_numbers, reason)


def best_match(target: VenueQuote, candidates: Iterable[VenueQuote]) -> tuple[VenueQuote | None, MatchDiagnostics]:
    best_quote = None
    best_diagnostics = MatchDiagnostics(0.0, 0.0, 0.0, 0.0, (), (), "no candidate evaluated")
    for candidate in candidates:
        diagnostics = compare_titles(target.title, candidate.title)
        if diagnostics.score > best_diagnostics.score:
            best_quote = candidate
            best_diagnostics = diagnostics
    return best_quote, best_diagnostics


def detect_opportunities(
    polymarket_quotes: list[VenueQuote],
    kalshi_quotes: list[VenueQuote],
    min_similarity: float = 0.72,
    min_edge: float = 0.02,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    for poly in polymarket_quotes:
        kalshi, diagnostics = best_match(poly, kalshi_quotes)
        if not kalshi or diagnostics.score < min_similarity:
            continue

        legs = [
            ("Buy YES on Polymarket + Buy NO on Kalshi", poly.yes_ask, kalshi.no_ask),
            ("Buy NO on Polymarket + Buy YES on Kalshi", poly.no_ask, kalshi.yes_ask),
        ]
        for strategy, first_leg, second_leg in legs:
            if first_leg is None or second_leg is None:
                continue
            total_cost = first_leg + second_leg
            locked_in_edge = 1.0 - total_cost
            if locked_in_edge < min_edge:
                continue
            poly_mid = poly.mid_price
            kalshi_mid = kalshi.mid_price
            price_dislocation = (
                abs(poly_mid - kalshi_mid)
                if poly_mid is not None and kalshi_mid is not None
                else None
            )
            opportunities.append(
                Opportunity(
                    polymarket=poly,
                    kalshi=kalshi,
                    strategy=strategy,
                    total_cost=total_cost,
                    locked_in_edge=locked_in_edge,
                    price_dislocation=price_dislocation,
                    diagnostics=diagnostics,
                )
            )

    opportunities.sort(
        key=lambda item: (item.locked_in_edge, item.diagnostics.score, item.price_dislocation or 0.0),
        reverse=True,
    )
    return opportunities


def format_probability(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:5.1f}%"


def render_opportunities_text(result: ScanResult, limit: int) -> str:
    if result.error:
        return result.error
    if not result.opportunities:
        message = "No cross-exchange opportunities matched the configured thresholds."
        if result.warning:
            return f"{message}\nWarning: {result.warning}"
        return message

    header = [
        f"Source mode: {result.source_mode}",
        f"Polymarket markets: {result.polymarket_count} | Kalshi markets: {result.kalshi_count}",
    ]
    if result.warning:
        header.append(f"Warning: {result.warning}")
    header.append("")

    lines = list(header)
    for index, opportunity in enumerate(result.opportunities[:limit], start=1):
        diag = opportunity.diagnostics
        lines.extend(
            [
                f"[{index}] {opportunity.polymarket.title}",
                f"  Strategy: {opportunity.strategy}",
                f"  Locked-in edge: {opportunity.locked_in_edge * 100:.2f}% | Total cost: {opportunity.total_cost * 100:.2f}%",
                f"  Match score: {diag.score:.2f} | Token overlap: {diag.token_jaccard:.2f} | Sequence: {diag.sequence_score:.2f} | Numeric: {diag.numeric_score:.2f}",
                f"  Shared tokens: {', '.join(diag.shared_tokens) or 'n/a'}",
                f"  Polymarket YES bid/ask: {format_probability(opportunity.polymarket.yes_bid)} / {format_probability(opportunity.polymarket.yes_ask)}",
                f"  Kalshi YES bid/ask:    {format_probability(opportunity.kalshi.yes_bid)} / {format_probability(opportunity.kalshi.yes_ask)}",
                f"  Polymarket: {opportunity.polymarket.url}",
                f"  Kalshi:     {opportunity.kalshi.url}",
            ]
        )
        if opportunity.price_dislocation is not None:
            lines.append(f"  YES mid-price dislocation: {opportunity.price_dislocation * 100:.2f}%")
        lines.append("")
    return "\n".join(lines).rstrip()


def opportunity_to_dict(opportunity: Opportunity) -> dict[str, object]:
    data = asdict(opportunity)
    return data


def render_dashboard_rows(opportunities: list[Opportunity], limit: int) -> str:
    rows = []
    for item in opportunities[:limit]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.polymarket.title)}</td>"
            f"<td>{html.escape(item.strategy)}</td>"
            f"<td>{item.locked_in_edge * 100:.2f}%</td>"
            f"<td>{item.diagnostics.score:.2f}</td>"
            f"<td>{', '.join(html.escape(token) for token in item.diagnostics.shared_tokens) or 'n/a'}</td>"
            f"<td><a href='{html.escape(item.polymarket.url)}' target='_blank' rel='noreferrer'>Polymarket</a></td>"
            f"<td><a href='{html.escape(item.kalshi.url)}' target='_blank' rel='noreferrer'>Kalshi</a></td>"
            "</tr>"
        )
    return "\n".join(rows)


def scan_result_to_json(result: ScanResult, limit: int) -> str:
    payload = {
        "source_mode": result.source_mode,
        "polymarket_count": result.polymarket_count,
        "kalshi_count": result.kalshi_count,
        "warning": result.warning,
        "error": result.error,
        "opportunities": [opportunity_to_dict(item) for item in result.opportunities[:limit]],
    }
    return json.dumps(payload, indent=2)
