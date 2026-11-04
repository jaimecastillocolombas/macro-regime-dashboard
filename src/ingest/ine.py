"""INE ingestion (Tempus JSON API, no API key).

Like the ECB, INE keeps no release history: ``available_at`` is the series lag capped by the
day we downloaded the value. The latest month is usually the provisional flash estimate
(``FK_TipoDato`` 3); when the final figure differs, the upsert treats it as a revision.
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

BASE_URL = "https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE"
FULL_HISTORY = "19000101:"  # open-ended date range: every observation of the series


def fetch_series(session: requests.Session, code: str) -> dict[str, Any]:
    """Raw JSON for one series code, e.g. ``IPC290750``."""
    response = session.get(
        f"{BASE_URL}/{code}", params={"date": FULL_HISTORY}, timeout=DEFAULT_TIMEOUT
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:  # INE answers unknown codes with HTTP 200 and an empty body
        payload = None
    if not isinstance(payload, dict) or "Data" not in payload:
        raise RuntimeError(f"INE returned no data for {code}")
    return payload


def parse_monthly(payload: dict[str, Any]) -> pd.Series:
    """Values indexed by the first day of the month.

    The period is built from ``Anyo`` and ``FK_Periodo``: ``Fecha`` is an epoch in Madrid time
    and is missing before 1970.
    """
    rows = [o for o in payload["Data"] if o["Valor"] is not None]
    if any(not 1 <= o["FK_Periodo"] <= 12 for o in rows):
        raise ValueError(f"{payload['COD']} is not a monthly series")
    return pd.Series(
        [float(o["Valor"]) for o in rows],
        index=pd.to_datetime([f"{o['Anyo']}-{o['FK_Periodo']:02d}-01" for o in rows]),
        name="value",
        dtype="float64",
    )


def ingest_series(
    engine: Engine,
    session: requests.Session,
    spec: SeriesSpec,
    retrieved_at: datetime | None = None,
) -> UpsertResult:
    """Download one INE series and upsert it (metadata first, then observations)."""
    retrieved_at = retrieved_at or datetime.now(UTC)
    values = parse_monthly(fetch_series(session, spec.source_key))
    rows = build_rows(spec, values, retrieved_at, seen_on=retrieved_at.date())
    upsert_series(engine, [spec.metadata_row()])
    return upsert_observations(engine, rows)
