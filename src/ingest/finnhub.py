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
MACRO_KEYWORDS = (
    # central banks and rates
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
    # prices
    "inflation",
    "deflation",
    "CPI",
    "prices",
    # bonds and debt
    "bond",
    "bonds",
    "yield",
    "yields",
    "Treasury",
    "Treasuries",
    "debt",
    "fiscal",
    # activity
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
    # markets
    "markets",
    "stocks",
    "stock market",
    "Wall Street",
    "oil",
    "gold",
    "dollar",
    "currency",
    # regions
    "euro zone",
    "euro area",
    "eurozone",
    "Spain",
)
_KEYWORDS = re.compile(r"\b(" + "|".join(re.escape(k) for k in MACRO_KEYWORDS) + r")\b", re.I)


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
    """Macro-relevant items, newest first, without duplicate headlines."""
    columns = ["published", "source", "headline", "summary", "url"]
    keep = [i for i in items if _KEYWORDS.search(f"{i['headline']} {i['summary']}")]
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
