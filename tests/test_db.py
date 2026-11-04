"""Tests for the schema, the idempotent upsert and the revision policy."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.dialects import postgresql

from src.db import (
    build_observation_upsert,
    get_engine,
    latest_available,
    observations,
    series,
    upsert_observations,
    upsert_series,
)

SERIES = {
    "series_id": "DGS10",
    "source": "FRED",
    "name": "US 10-year Treasury yield",
    "unit": "percent",
    "frequency": "daily",
    "country": "US",
    "publication_lag_days": 1,
}
RUN_1 = datetime(2026, 11, 2, 22, 0, tzinfo=UTC)
RUN_2 = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)


def obs(day: int, value: float, available: date, retrieved: datetime = RUN_1) -> dict:
    return {
        "series_id": "DGS10",
        "date": date(2026, 10, day),
        "value": value,
        "available_at": available,
        "retrieved_at": retrieved,
    }


@pytest.fixture
def engine(tmp_path) -> Engine:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    upsert_series(engine, [SERIES])
    return engine


def count_rows(engine: Engine, table) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def test_first_load_inserts_everything(engine: Engine) -> None:
    result = upsert_observations(
        engine, [obs(1, 4.10, date(2026, 10, 2)), obs(2, 4.15, date(2026, 10, 3))]
    )
    assert (result.inserted, result.updated) == (2, 0)
    assert count_rows(engine, observations) == 2


def test_running_twice_does_not_duplicate(engine: Engine) -> None:
    rows = [obs(1, 4.10, date(2026, 10, 2)), obs(2, 4.15, date(2026, 10, 3))]
    upsert_observations(engine, rows)
    result = upsert_observations(engine, rows)
    assert (result.inserted, result.updated) == (0, 2)
    assert count_rows(engine, observations) == 2


def test_unchanged_value_keeps_original_available_at(engine: Engine) -> None:
    upsert_observations(engine, [obs(1, 4.10, date(2026, 10, 2))])
    upsert_observations(engine, [obs(1, 4.10, date(2026, 11, 3), retrieved=RUN_2)])
    with engine.connect() as conn:
        row = conn.execute(select(observations)).one()
    assert row.available_at == date(2026, 10, 2)
    assert row.retrieved_at.replace(tzinfo=UTC) == RUN_2


def test_revised_value_moves_available_at_to_the_revision(engine: Engine) -> None:
    upsert_observations(engine, [obs(1, 4.10, date(2026, 10, 2))])
    upsert_observations(engine, [obs(1, 4.12, date(2026, 11, 3), retrieved=RUN_2)])
    with engine.connect() as conn:
        row = conn.execute(select(observations)).one()
    assert (row.value, row.available_at) == (4.12, date(2026, 11, 3))


def test_point_in_time_view_hides_future_releases(engine: Engine) -> None:
    upsert_observations(engine, [obs(1, 4.10, date(2026, 10, 2)), obs(2, 4.15, date(2026, 10, 3))])
    assert latest_available(engine, "DGS10", as_of=date(2026, 10, 2)) == [(date(2026, 10, 1), 4.10)]


def test_series_metadata_is_refreshed_not_duplicated(engine: Engine) -> None:
    upsert_series(engine, [{**SERIES, "name": "10-Year Treasury Constant Maturity"}])
    assert count_rows(engine, series) == 1
    with engine.connect() as conn:
        assert (
            conn.execute(select(series.c.name)).scalar_one() == "10-Year Treasury Constant Maturity"
        )


def test_empty_input_is_a_no_op(engine: Engine) -> None:
    result = upsert_observations(engine, [])
    assert (result.inserted, result.updated) == (0, 0)


def test_postgres_statement_uses_on_conflict() -> None:
    """CI has no Postgres: check the SQL the Postgres dialect would send instead."""

    class FakePostgresEngine:
        class dialect:  # noqa: N801 - mimics engine.dialect.name
            name = "postgresql"

    stmt = build_observation_upsert(FakePostgresEngine())  # type: ignore[arg-type]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (series_id, date) DO UPDATE" in sql
    assert "CASE WHEN" in sql
