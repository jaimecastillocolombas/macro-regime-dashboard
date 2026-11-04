"""FRED ingestion.

``value`` is always the current vintage. ``available_at`` depends on the frequency:

- monthly series: the date of the *first* release, from ALFRED (``output_type=4``); dates older
  than the first vintage fall back to ``date + publication_lag_days`` (calendar days);
- daily series: ``date + publication_lag_days`` business days (they have thousands of vintages
  and are not revised, so ALFRED adds nothing).
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests
from sqlalchemy import Engine

from src.config import SeriesSpec
from src.db import UpsertResult, upsert_observations, upsert_series
from src.ingest.availability import build_rows
from src.ingest.http import DEFAULT_TIMEOUT

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
ALL_TIME = {
    "realtime_start": "1776-07-04",
    "realtime_end": "9999-12-31",
}  # FRED's documented bounds
MISSING = "."  # FRED's marker for a missing value


# ----------------------------------------------------------------------------- network


def fetch_observations(
    session: requests.Session, series_id: str, api_key: str, **params: Any
) -> dict[str, Any]:
    """Raw JSON from /fred/series/observations. Raises on HTTP errors."""
    query = {"series_id": series_id, "api_key": api_key, "file_type": "json", **params}
    response = session.get(BASE_URL, params=query, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()


# ----------------------------------------------------------------------------- pure parsing


def parse_values(payload: dict[str, Any]) -> pd.Series:
    """Current-vintage values indexed by reference date; FRED's '.' gaps are dropped."""
    rows = [o for o in payload["observations"] if o["value"] != MISSING]
    return pd.Series(
        [float(o["value"]) for o in rows],
        index=pd.to_datetime([o["date"] for o in rows]),
        name="value",
        dtype="float64",
    )


def parse_first_release(payload: dict[str, Any]) -> pd.Series:
    """First-release date (``realtime_start``) indexed by reference date."""
    obs = payload["observations"]
    return pd.Series(
        pd.to_datetime([o["realtime_start"] for o in obs]),
        index=pd.to_datetime([o["date"] for o in obs]),
        name="available_at",
    )


# ----------------------------------------------------------------------------- orchestration


def ingest_series(
    engine: Engine,
    session: requests.Session,
    spec: SeriesSpec,
    api_key: str,
    retrieved_at: datetime | None = None,
) -> UpsertResult:
    """Download one FRED series and upsert it (metadata first, then observations)."""
    retrieved_at = retrieved_at or datetime.now(UTC)
    values = parse_values(fetch_observations(session, spec.series_id, api_key))
    first_release = None
    if spec.frequency == "monthly":
        payload = fetch_observations(session, spec.series_id, api_key, output_type=4, **ALL_TIME)
        first_release = parse_first_release(payload)
    upsert_series(engine, [spec.metadata_row()])
    return upsert_observations(engine, build_rows(spec, values, retrieved_at, first_release))
