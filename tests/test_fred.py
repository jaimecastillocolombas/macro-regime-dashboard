"""FRED ingestion tests, built on real API responses saved in tests/fixtures (no network)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import func, select

from src.config import FRED_SERIES
from src.db import get_engine, observations
from src.ingest.fred import build_rows, ingest_series, parse_first_release, parse_values

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = {s.series_id: s for s in FRED_SERIES}
RETRIEVED = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def rows_by_date(rows: list[dict]) -> dict[date, dict]:
    return {r["date"]: r for r in rows}


# ----------------------------------------------------------------------------- parsing


def test_missing_values_are_dropped() -> None:
    values = parse_values(load("fred_DGS10_observations.json"))
    assert len(values) == 10  # 12 observations, Christmas and New Year's Day are '.'
    assert pd.Timestamp("2025-12-25") not in values.index
    assert values[pd.Timestamp("2025-12-22")] == pytest.approx(4.17)


def test_default_realtime_start_is_not_used_as_availability() -> None:
    """The plain endpoint stamps every row with today's date: using it would hide all history."""
    payload = load("fred_DGS10_observations.json")
    assert {o["realtime_start"] for o in payload["observations"]} == {"2026-11-04"}
    rows = build_rows(SPECS["DGS10"], parse_values(payload), RETRIEVED)
    assert rows_by_date(rows)[date(2025, 12, 22)]["available_at"] == date(2025, 12, 23)


# ----------------------------------------------------------------------------- available_at


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (date(2025, 12, 22), date(2025, 12, 23)),  # Monday -> Tuesday
        (date(2025, 12, 24), date(2025, 12, 26)),  # skips Christmas
        (date(2025, 12, 26), date(2025, 12, 29)),  # Friday -> Monday
        (date(2025, 12, 31), date(2026, 1, 2)),  # skips New Year's Day
    ],
)
def test_daily_series_use_us_business_days(reference: date, expected: date) -> None:
    rows = build_rows(SPECS["DGS10"], parse_values(load("fred_DGS10_observations.json")), RETRIEVED)
    assert rows_by_date(rows)[reference]["available_at"] == expected


def test_monthly_series_use_first_release_and_fall_back_to_the_lag() -> None:
    values = parse_values(load("fred_CPILFENS_observations.json"))
    first = parse_first_release(load("fred_CPILFENS_first_release.json"))
    rows = rows_by_date(build_rows(SPECS["CPILFENS"], values, RETRIEVED, first))
    # ALFRED vintages for core CPI start with the Dec-1996 release
    assert rows[date(1996, 12, 1)]["available_at"] == date(1997, 1, 14)
    assert rows[date(1997, 2, 1)]["available_at"] == date(1997, 3, 19)
    # Earlier months have no vintage: conservative 60-day fallback
    assert rows[date(1996, 9, 1)]["available_at"] == date(1996, 10, 31)


def test_value_is_the_current_vintage() -> None:
    values = parse_values(load("fred_CPILFENS_observations.json"))
    first = parse_first_release(load("fred_CPILFENS_first_release.json"))
    rows = rows_by_date(build_rows(SPECS["CPILFENS"], values, RETRIEVED, first))
    assert rows[date(1997, 1, 1)]["value"] == pytest.approx(167.5)


def test_nothing_is_available_before_its_reference_date() -> None:
    values = parse_values(load("fred_CPILFENS_observations.json"))
    rows = build_rows(SPECS["CPILFENS"], values, RETRIEVED)
    assert all(r["available_at"] >= r["date"] for r in rows)


# ----------------------------------------------------------------------------- end to end


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    """Serves the saved fixtures instead of calling FRED."""

    def get(self, url: str, params: dict, timeout: int) -> FakeResponse:
        kind = "first_release" if params.get("output_type") == 4 else "observations"
        return FakeResponse(load(f"fred_{params['series_id']}_{kind}.json"))


def test_ingesting_twice_is_idempotent(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    session = FakeSession()
    first = ingest_series(engine, session, SPECS["CPILFENS"], "test-key", RETRIEVED)
    second = ingest_series(engine, session, SPECS["CPILFENS"], "test-key", RETRIEVED)
    assert (first.inserted, first.updated) == (6, 0)
    assert (second.inserted, second.updated) == (0, 6)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(observations)).scalar_one() == 6
