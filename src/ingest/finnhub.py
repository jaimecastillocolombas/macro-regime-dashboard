"""Finnhub market news, fetched live by the app (not stored).

The API key travels in the ``X-Finnhub-Token`` header, never in the URL, so it cannot leak into
error messages or logs.
"""

import re
from typing import Any

import pandas as pd
import requests

from src.ingest.http import DEFAULT_TIMEOUT

NEWS_URL = "https://finnhub.io/api/v1/news"

# A headline or summary must mention one of these to count as macro news (whole words,
# case-insensitive). Company results, deals and politics without a market angle are left out.
# Checked on 2026-11-05: the narrow policy-only list kept 3 of 100 items, this one keeps 30.
# The keywords are grouped into the topic each story is tagged with. Topics are tried in this
# order, most specific first, so "ECB worries about the economy" is central-bank news and the
# broad "Markets" only catches what nothing else did.
TOPICS: dict[str, tuple[str, ...]] = {
    "Central banks": (
        "Fed",
        "Federal Reserve",
        "ECB",
        "central bank",
        "Powell",
        "Lagarde",
        "interest rate",
        "interest rates",
        "rate cut",
        "rate cuts",
        "rate hike",
        "rate hikes",
    ),
    "Inflation": ("inflation", "deflation", "CPI", "prices"),
    "Bonds": ("bond", "bonds", "yield", "yields", "Treasury", "Treasuries", "debt", "fiscal"),
    "Europe": ("euro zone", "euro area", "eurozone", "Spain"),
    "Economy": (
        "economy",
        "economic",
        "recession",
        "GDP",
        "unemployment",
        "payrolls",
        "jobs report",
        "trade",
        "tariff",
        "tariffs",
    ),
    "Markets": (
        "markets",
        "stocks",
        "stock market",
        "Wall Street",
        "oil",
        "gold",
        "dollar",
        "currency",
    ),
}
_PATTERNS = {
    topic: re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.I)
    for topic, keywords in TOPICS.items()
}


def topic_of(headline: str, summary: str = "") -> str | None:
    """First topic (in TOPICS order) whose keywords the headline mentions, else the summary;
    None when neither is macro news. The headline wins because it says what the story is about,
    while summaries often mention markets in passing."""
    for text in (headline, summary):
        for topic, pattern in _PATTERNS.items():
            if pattern.search(text):
                return topic
    return None


def fetch_news(session: requests.Session, api_key: str, category: str = "general") -> list[dict]:
    """Latest market news (about 100 items covering the last day or two)."""
    response = session.get(
        NEWS_URL,
        params={"category": category},
        headers={"X-Finnhub-Token": api_key},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):  # errors come back as {"error": "..."} with HTTP 200
        raise RuntimeError(f"Finnhub returned no news: {str(payload)[:200]}")
    return payload


def relevant_news(items: list[dict[str, Any]], limit: int = 25) -> pd.DataFrame:
    """Macro-relevant items tagged with their topic, newest first, without duplicate
    headlines."""
    columns = ["published", "source", "topic", "headline", "summary", "url", "image"]
    keep = [i | {"topic": topic_of(i["headline"], i["summary"])} for i in items]
    keep = [i for i in keep if i["topic"]]
    if not keep:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(keep)
    frame["published"] = pd.to_datetime(frame["datetime"], unit="s", utc=True)
    # Reuters appends " - Reuters" to headlines and often repeats the headline as summary
    frame["headline"] = [
        h.removesuffix(f" - {s}").strip()
        for h, s in zip(frame["headline"], frame["source"], strict=True)
    ]
    frame["summary"] = [
        "" if s.strip().startswith(h) else s.strip()
        for h, s in zip(frame["headline"], frame["summary"], strict=True)
    ]
    frame = frame.sort_values("published", ascending=False).drop_duplicates("headline")
    return frame[columns].head(limit).reset_index(drop=True)
