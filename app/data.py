"""Cached reads for the app. All logic lives in src/; this module only loads and caches."""

import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from src.db import freshness, get_engine, read_observations
from src.transform.series import from_long


@st.cache_resource
def engine() -> Engine:
    return get_engine()


@st.cache_data(ttl=3600)
def load(series_ids: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Stored series by id; refreshed at most once an hour (the data changes once a day)."""
    long = read_observations(engine(), list(series_ids))
    return {series_id: from_long(long, series_id) for series_id in series_ids}


@st.cache_data(ttl=600)
def source_freshness() -> pd.DataFrame:
    """Last download and latest observation per source; refreshed every 10 minutes."""
    return freshness(engine())
