"""ECB Data Portal ingestion (SDMX REST, CSV format, no API key).

The ECB keeps no release history, so ``available_at`` is the fixed lag of each series, capped
by the day we downloaded the value: history gets the conservative lag and, from the first
scheduled run on, new values get the day they were actually seen.
"""

import io
import time
from datetime import UTC, datetime

import pandas as pd
import requests
from sqlalchemy import Engine

from src.config import SeriesSpec
from src.db import UpsertResult, upsert_observations, upsert_series
from src.ingest.availability import build_rows
from src.ingest.http import DEFAULT_TIMEOUT

BASE_URL = "https://data-api.ecb.europa.eu/service/data"
PAUSE_SECONDS = 2.0  # the portal's firewall blocks bursts of requests with an HTML 400 page


def fetch_csv(session: requests.Session, key: str) -> str:
    """Raw CSV for one series key, e.g. ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y``."""
    response = session.get(
        f"{BASE_URL}/{key}",
        params={"format": "csvdata", "detail": "dataonly"},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    if not response.text.startswith("KEY,"):
        raise RuntimeError(f"ECB returned a non-CSV response for {key} (firewall block?)")
    return response.text


def parse_csv(text: str) -> pd.Series:
    """Values indexed by reference date; a month ``2026-10`` becomes ``2026-10-01``."""
    frame = pd.read_csv(io.StringIO(text), usecols=["TIME_PERIOD", "OBS_VALUE"])
    frame = frame.dropna(subset=["OBS_VALUE"])
    return pd.Series(
        frame["OBS_VALUE"].astype("float64").to_numpy(),
        index=pd.to_datetime(frame["TIME_PERIOD"]),
        name="value",
    )


def ingest_series(
    engine: Engine,
    session: requests.Session,
    spec: SeriesSpec,
    retrieved_at: datetime | None = None,
) -> UpsertResult:
    """Download one ECB series and upsert it (metadata first, then observations)."""
    retrieved_at = retrieved_at or datetime.now(UTC)
    values = parse_csv(fetch_csv(session, spec.source_key))
    rows = build_rows(spec, values, retrieved_at, seen_on=retrieved_at.date())
    upsert_series(engine, [spec.metadata_row()])
    return upsert_observations(engine, rows)


def ingest_all(
    engine: Engine, session: requests.Session, specs: tuple[SeriesSpec, ...]
) -> dict[str, UpsertResult]:
    """Ingest series one after another, pausing between requests to stay under the firewall."""
    results = {}
    for i, spec in enumerate(specs):
        if i:
            time.sleep(PAUSE_SECONDS)
        results[spec.series_id] = ingest_series(engine, session, spec)
    return results
