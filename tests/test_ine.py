"""INE ingestion tests, built on real API responses saved in tests/fixtures (no network)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.config import INE_SERIES
from src.db import get_engine
from src.ingest.availability import build_rows
from src.ingest.ine import fetch_series, ingest_series, parse_monthly

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = {s.series_id: s for s in INE_SERIES}
RETRIEVED = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_period_comes_from_year_and_month_even_before_1970() -> None:
    """Records before 1970 have no ``Fecha`` field at all."""
    payload = load("ine_IPC290750_1962.json")
    assert "Fecha" not in payload["Data"][0]
    values = parse_monthly(payload)
    assert values.index[0] == pd.Timestamp("1962-01-01")
    assert values[pd.Timestamp("1962-03-01")] == pytest.approx(3.0)


def test_month_is_not_shifted_by_the_madrid_timezone() -> None:
    """``Fecha`` for October 2026 is 2026-09-30T22:00Z; the period must still be October."""
    values = parse_monthly(load("ine_IPC292510_last4.json"))
    assert values.index[-1] == pd.Timestamp("2026-10-01")
    assert values.iloc[-1] == pytest.approx(3.1)


def test_history_uses_the_lag_and_the_flash_the_day_it_was_seen() -> None:
    values = parse_monthly(load("ine_IPC292510_last4.json"))
    rows = build_rows(SPECS["ES_CPI_CORE"], values, RETRIEVED, seen_on=RETRIEVED.date())
    by_date = {r["date"]: r for r in rows}
    assert by_date[date(2026, 7, 1)]["available_at"] == date(2026, 8, 20)  # 50-day lag
    assert by_date[date(2026, 10, 1)]["available_at"] == date(2026, 11, 4)  # provisional flash


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        if self.payload is None:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self.payload


class FakeSession:
    def __init__(self, payload) -> None:
        self.payload = payload

    def get(self, url: str, params: dict, timeout: int) -> FakeResponse:
        return FakeResponse(self.payload)


def test_unknown_code_is_an_error_not_empty_data() -> None:
    """INE answers an unknown code with HTTP 200 and an empty body."""
    session = FakeSession(None)
    with pytest.raises(RuntimeError, match="no data"):
        fetch_series(session, "IPC000000")


def test_ingesting_twice_is_idempotent(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    session = FakeSession(load("ine_IPC292510_last4.json"))
    first = ingest_series(engine, session, SPECS["ES_CPI_CORE"], RETRIEVED)
    second = ingest_series(engine, session, SPECS["ES_CPI_CORE"], RETRIEVED)
    assert (first.inserted, first.updated) == (4, 0)
    assert (second.inserted, second.updated) == (0, 4)
