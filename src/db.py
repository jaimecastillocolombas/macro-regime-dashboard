"""Database schema and idempotent upserts, portable between SQLite and Postgres.

Two tables:
- ``series``: one row of metadata per series.
- ``observations``: one value per (series_id, date). ``date`` is the reference period of the
  value; ``available_at`` is when it became public. They are never mixed: signals filter on
  ``available_at`` to avoid look-ahead bias.

Revision policy: re-ingesting an unchanged value is a no-op for ``value`` and ``available_at``
(only ``retrieved_at`` moves). If the value changes, it is treated as a revision and its
``available_at`` moves to the new release, so a backtest cannot see it earlier.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    case,
    create_engine,
    func,
    select,
    tuple_,
)
from sqlalchemy.dialects import postgresql, sqlite

from src.config import database_url

BATCH_SIZE = 500  # keeps SQLite under its bound-parameter limit

metadata = MetaData()

series = Table(
    "series",
    metadata,
    Column("series_id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("name", String, nullable=False),
    Column("unit", String, nullable=False),
    Column("frequency", String, nullable=False),
    Column("country", String, nullable=False),
    Column("publication_lag_days", Integer, nullable=False),
)

observations = Table(
    "observations",
    metadata,
    Column("series_id", String, ForeignKey("series.series_id"), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("value", Float, nullable=False),
    Column("available_at", Date, nullable=False),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class UpsertResult:
    inserted: int
    updated: int


def get_engine(url: str | None = None) -> Engine:
    """Create an engine for ``url`` (or DATABASE_URL), making sure the tables exist."""
    engine = create_engine(url or database_url())
    metadata.create_all(engine)
    return engine


def _insert_for(engine: Engine, table: Table) -> Any:
    """Dialect-specific INSERT, the only one that supports ON CONFLICT DO UPDATE."""
    dialects = {"sqlite": sqlite.insert, "postgresql": postgresql.insert}
    try:
        return dialects[engine.dialect.name](table)
    except KeyError as exc:
        raise NotImplementedError(f"Unsupported database: {engine.dialect.name}") from exc


def _batches(
    rows: Sequence[dict[str, Any]], size: int = BATCH_SIZE
) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def upsert_series(engine: Engine, rows: Sequence[dict[str, Any]]) -> None:
    """Insert or refresh series metadata (metadata always takes the latest definition)."""
    if not rows:
        return
    stmt = _insert_for(engine, series)
    stmt = stmt.on_conflict_do_update(
        index_elements=[series.c.series_id],
        set_={c.name: stmt.excluded[c.name] for c in series.columns if c.name != "series_id"},
    )
    with engine.begin() as conn:
        for batch in _batches(rows):
            conn.execute(stmt, batch)


def build_observation_upsert(engine: Engine) -> Any:
    """ON CONFLICT statement implementing the revision policy described in the module docstring."""
    stmt = _insert_for(engine, observations)
    new, old = stmt.excluded, observations.c
    changed = new.value != old.value
    return stmt.on_conflict_do_update(
        index_elements=[old.series_id, old.date],
        set_={
            "value": new.value,
            "available_at": case((changed, new.available_at), else_=old.available_at),
            "retrieved_at": new.retrieved_at,
        },
    )


def upsert_observations(engine: Engine, rows: Sequence[dict[str, Any]]) -> UpsertResult:
    """Idempotently write observations; return how many keys were new and how many existed.

    Each row needs: series_id, date, value, available_at, retrieved_at.
    """
    if not rows:
        return UpsertResult(inserted=0, updated=0)
    stmt = build_observation_upsert(engine)
    existing = 0
    with engine.begin() as conn:
        for batch in _batches(rows):
            keys = [(r["series_id"], r["date"]) for r in batch]
            already_there = select(observations.c.series_id).where(
                tuple_(observations.c.series_id, observations.c.date).in_(keys)
            )
            existing += len(conn.execute(already_there).all())
            conn.execute(stmt, batch)
    return UpsertResult(inserted=len(rows) - existing, updated=existing)


def latest_available(engine: Engine, series_id: str, as_of: date) -> list[tuple[date, float]]:
    """Point-in-time view: the observations of a series that were public on ``as_of``."""
    query = (
        select(observations.c.date, observations.c.value)
        .where(and_(observations.c.series_id == series_id, observations.c.available_at <= as_of))
        .order_by(observations.c.date)
    )
    with engine.connect() as conn:
        return [(row.date, row.value) for row in conn.execute(query)]


def read_observations(
    engine: Engine, series_ids: Sequence[str], as_of: date | None = None
) -> pd.DataFrame:
    """Long frame (series_id, date, value, available_at) for the given series.

    With ``as_of``, only what was public on that day: the point-in-time view for backtests.
    """
    query = select(
        observations.c.series_id,
        observations.c.date,
        observations.c.value,
        observations.c.available_at,
    ).where(observations.c.series_id.in_(series_ids))
    if as_of is not None:
        query = query.where(observations.c.available_at <= as_of)
    with engine.connect() as conn:
        frame = pd.DataFrame(conn.execute(query.order_by(observations.c.date)).all())
    if frame.empty:
        return pd.DataFrame(columns=["series_id", "date", "value", "available_at"])
    frame["date"] = pd.to_datetime(frame["date"])
    frame["available_at"] = pd.to_datetime(frame["available_at"])
    return frame


def freshness(engine: Engine) -> pd.DataFrame:
    """Per source and frequency: last successful download (UTC) and latest observation date.

    The upsert stamps ``retrieved_at`` on every row it writes, so its maximum is the last time
    any series of that group was ingested. Frequencies are kept apart because one date per
    source would hide that, say, US CPI is a month behind the daily yields.
    """
    query = (
        select(
            series.c.source,
            series.c.frequency,
            func.max(observations.c.retrieved_at).label("retrieved_at"),
            func.max(observations.c.date).label("latest_date"),
        )
        .join(observations, observations.c.series_id == series.c.series_id)
        .group_by(series.c.source, series.c.frequency)
        .order_by(series.c.source, series.c.frequency)
    )
    with engine.connect() as conn:
        rows = conn.execute(query).all()
    frame = pd.DataFrame(rows, columns=["source", "frequency", "retrieved_at", "latest_date"])
    # SQLite drops the timezone on read; every timestamp we write is UTC
    frame["retrieved_at"] = pd.to_datetime(frame["retrieved_at"], utc=True)
    frame["latest_date"] = pd.to_datetime(frame["latest_date"])
    return frame
