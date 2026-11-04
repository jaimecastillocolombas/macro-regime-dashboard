"""Pipeline runner tests with fake ingesters (no network)."""

from datetime import UTC, date, datetime

from src.config import ECB_SERIES, FRED_SERIES
from src.db import UpsertResult, get_engine, upsert_observations, upsert_series
from src.ingest.run import PAUSES, run_all, summary_table

RETRIEVED = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)


def store_one(engine, spec) -> UpsertResult:
    upsert_series(engine, [spec.metadata_row()])
    row = {
        "series_id": spec.series_id,
        "date": date(2026, 11, 3),
        "value": 1.0,
        "available_at": date(2026, 11, 4),
        "retrieved_at": RETRIEVED,
    }
    return upsert_observations(engine, [row])


def fail(engine, spec) -> UpsertResult:
    raise RuntimeError("ECB returned a non-CSV response")


def test_one_failure_does_not_stop_the_other_series(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    jobs = [(FRED_SERIES[0], store_one), (ECB_SERIES[0], fail), (ECB_SERIES[1], store_one)]
    reports = run_all(engine, jobs, sleep=lambda _: None)
    assert [r.error is None for r in reports] == [True, False, True]
    assert reports[1].error == "RuntimeError: ECB returned a non-CSV response"
    assert (reports[2].inserted, reports[2].last_date) == (1, date(2026, 11, 3))
    assert "non-CSV" in summary_table(reports)


def test_requests_to_the_ecb_are_spaced_out(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    waits: list[float] = []
    jobs = [(FRED_SERIES[0], store_one), *[(spec, store_one) for spec in ECB_SERIES[:3]]]
    run_all(engine, jobs, sleep=waits.append)
    assert waits == [PAUSES["ECB"]] * 2  # between ECB requests only, not before the first
