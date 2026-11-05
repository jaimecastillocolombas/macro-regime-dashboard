"""Cached reads for the app. All logic lives in src/; this module only loads and caches."""

import os

import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from src.db import freshness, get_engine, read_observations
from src.ingest.finnhub import fetch_news, relevant_news
from src.ingest.http import make_session
from src.transform.series import from_long


def secret(name: str) -> str | None:
    """A setting from the environment or, on Streamlit Cloud, from the app's secrets."""
    if value := os.getenv(name):
        return value
    try:
        return st.secrets.get(name)
    except FileNotFoundError:  # no secrets file at all, the normal case locally
        return None


def database_url() -> str | None:
    """None means "not configured": src.config then falls back to the local SQLite file."""
    return secret("DATABASE_URL")


# Every cache below is keyed by the database URL, so changing the DATABASE_URL secret takes
# effect on the next run instead of reusing a connection (or an empty result) from before.


@st.cache_resource
def _engine(url: str | None) -> Engine:
    return get_engine(url)


@st.cache_data(ttl=3600)
def _load(series_ids: tuple[str, ...], url: str | None) -> dict[str, pd.DataFrame]:
    long = read_observations(_engine(url), list(series_ids))
    return {series_id: from_long(long, series_id) for series_id in series_ids}


@st.cache_data(ttl=600)
def _freshness(url: str | None) -> pd.DataFrame:
    return freshness(_engine(url))


def load(series_ids: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Stored series by id; refreshed at most once an hour (the data changes once a day)."""
    return _load(series_ids, database_url())


def source_freshness() -> pd.DataFrame:
    """Last download and latest observation per source; refreshed every 10 minutes."""
    return _freshness(database_url())


@st.cache_data(ttl=900, show_spinner=False)
def _raw_news(api_key: str) -> list[dict]:
    # Only Finnhub's raw payload is cached. Streamlit keys the cache on this function's own
    # source, not on what it calls, so caching relevant_news' output kept serving the old
    # columns after the filter changed (KeyError: 'topic' on the live app).
    return fetch_news(make_session(), api_key)


def news() -> pd.DataFrame | None:
    """Macro news from Finnhub, refreshed at most every 15 minutes; None without an API key.
    Filtering and tagging are cheap and pure, so they run on every rerun with the current code.
    """
    api_key = secret("FINNHUB_API_KEY")
    return relevant_news(_raw_news(api_key)) if api_key else None
