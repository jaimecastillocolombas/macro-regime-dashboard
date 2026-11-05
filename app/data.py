"""Cached reads for the app. All logic lives in src/; this module only loads and caches."""

import os

import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from src.db import freshness, get_engine, read_observations
from src.transform.series import from_long


def database_url() -> str | None:
    """DATABASE_URL from the environment or, on Streamlit Cloud, from the app's secrets.

    None means "not configured": src.config then falls back to the local SQLite file.
    """
    if url := os.getenv("DATABASE_URL"):
        return url
    try:
        return st.secrets.get("DATABASE_URL")
    except FileNotFoundError:  # no secrets file at all, the normal case locally
        return None


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
