"""Pipeline entry point: ingest every series and print a summary.

    python -m src.ingest.run

One failing series does not stop the others. The exit code is 1 if any series failed, so the
scheduled workflow is marked as failed and GitHub sends a notification.
"""

import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests
from sqlalchemy import Engine, func, select

from src.config import ECB_SERIES, FRED_SERIES, INE_SERIES, SeriesSpec, fred_api_key
from src.db import UpsertResult, get_engine, observations
from src.ingest import ecb, fred, ine
from src.ingest.http import make_session

log = logging.getLogger(__name__)

Ingester = Callable[[Engine, SeriesSpec], UpsertResult]

# Seconds to wait between two requests to the same source
PAUSES = {"ECB": ecb.PAUSE_SECONDS}


@dataclass(frozen=True)
class SeriesReport:
    series_id: str
    source: str
    inserted: int = 0
    updated: int = 0
    last_date: date | None = None
    error: str | None = None


def build_jobs(session: requests.Session) -> list[tuple[SeriesSpec, Ingester]]:
    """Every series in the catalogue paired with the function that ingests it."""

    def fred_job(engine: Engine, spec: SeriesSpec) -> UpsertResult:
        # The key is read per series, so a missing key is reported instead of crashing the run
        return fred.ingest_series(engine, session, spec, fred_api_key())

    def ecb_job(engine: Engine, spec: SeriesSpec) -> UpsertResult:
        return ecb.ingest_series(engine, session, spec)

    def ine_job(engine: Engine, spec: SeriesSpec) -> UpsertResult:
        return ine.ingest_series(engine, session, spec)

    return (
        [(spec, fred_job) for spec in FRED_SERIES]
        + [(spec, ecb_job) for spec in ECB_SERIES]
        + [(spec, ine_job) for spec in INE_SERIES]
    )


def last_date(engine: Engine, series_id: str) -> date | None:
    query = select(func.max(observations.c.date)).where(observations.c.series_id == series_id)
    with engine.connect() as conn:
        return conn.execute(query).scalar_one()


def run_all(
    engine: Engine,
    jobs: Sequence[tuple[SeriesSpec, Ingester]],
    sleep: Callable[[float], None] = time.sleep,
) -> list[SeriesReport]:
    """Run every job, isolating failures, and report the outcome of each series."""
    reports = []
    previous_source = None
    for spec, ingest in jobs:
        if spec.source == previous_source and spec.source in PAUSES:
            sleep(PAUSES[spec.source])
        previous_source = spec.source
        try:
            result = ingest(engine, spec)
        except Exception as exc:  # report and carry on: one bad series must not stop the rest
            log.exception("Ingestion failed for %s", spec.series_id)
            error = f"{type(exc).__name__}: {exc}"
            reports.append(SeriesReport(spec.series_id, spec.source, error=error))
            continue
        reports.append(
            SeriesReport(
                spec.series_id,
                spec.source,
                result.inserted,
                result.updated,
                last_date(engine, spec.series_id),
            )
        )
    return reports


def summary_table(reports: Sequence[SeriesReport]) -> str:
    frame = pd.DataFrame([vars(r) for r in reports]).fillna({"error": ""})
    return frame.to_string(index=False)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    started = time.monotonic()
    reports = run_all(get_engine(), build_jobs(make_session()))
    failed = [r.series_id for r in reports if r.error]
    print(summary_table(reports))
    print(
        f"\n{len(reports) - len(failed)}/{len(reports)} series OK, "
        f"{sum(r.inserted for r in reports)} new rows, "
        f"{time.monotonic() - started:.0f}s"
    )
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
