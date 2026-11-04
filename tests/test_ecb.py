"""ECB ingestion tests, built on real API responses saved in tests/fixtures (no network)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.config import ECB_SERIES
from src.db import get_engine
from src.ingest.availability import TargetHolidayCalendar, add_business_days, build_rows
from src.ingest.ecb import fetch_csv, ingest_series, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = {s.series_id: s for s in ECB_SERIES}
RETRIEVED = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def rows_by_date(rows: list[dict]) -> dict[date, dict]:
    return {r["date"]: r for r in rows}


# ----------------------------------------------------------------------------- parsing


def test_daily_csv_is_parsed() -> None:
    values = parse_csv(load("ecb_YC_10Y.csv"))
    assert len(values) == 9  # no curve on TARGET holidays (Dec 25, Dec 26, Jan 1)
    assert values[pd.Timestamp("2025-12-22")] == pytest.approx(2.9967111658)


def test_monthly_periods_become_the_first_day_of_the_month() -> None:
    values = parse_csv(load("ecb_HICP_U2.csv"))
    assert values.index[-1] == pd.Timestamp("2026-10-01")
    assert values.iloc[-1] == pytest.approx(4.0)


# ----------------------------------------------------------------------------- available_at


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (date(2025, 12, 23), date(2025, 12, 24)),  # TARGET is open on Christmas Eve
        (date(2025, 12, 24), date(2025, 12, 29)),  # skips Dec 25, Dec 26 and the weekend
        (date(2025, 12, 31), date(2026, 1, 2)),  # skips New Year's Day
    ],
)
def test_daily_ecb_series_use_target_business_days(reference: date, expected: date) -> None:
    rows = build_rows(SPECS["EA_YC_10Y"], parse_csv(load("ecb_YC_10Y.csv")), RETRIEVED)
    assert rows_by_date(rows)[reference]["available_at"] == expected


def test_target_calendar_closes_on_easter() -> None:
    thursday = pd.DatetimeIndex(["2026-04-02"])  # Good Friday Apr 3, Easter Monday Apr 6
    assert add_business_days(thursday, 1, TargetHolidayCalendar())[0] == pd.Timestamp("2026-04-07")


def test_history_uses_the_lag_and_recent_values_the_day_they_were_seen() -> None:
    rows = rows_by_date(
        build_rows(
            SPECS["EA_HICP"],
            parse_csv(load("ecb_HICP_U2.csv")),
            RETRIEVED,
            seen_on=RETRIEVED.date(),
        )
    )
    assert rows[date(2026, 6, 1)]["available_at"] == date(2026, 7, 31)  # 60-day lag
    # October's flash estimate is already in our hands on Nov 4, before the lag expires
    assert rows[date(2026, 10, 1)]["available_at"] == date(2026, 11, 4)


# ----------------------------------------------------------------------------- end to end


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, url: str, params: dict, timeout: int) -> FakeResponse:
        return FakeResponse(self.text)


def test_firewall_html_page_is_an_error_not_data() -> None:
    session = FakeSession("<html><body>Your access has been blocked</body></html>")
    with pytest.raises(RuntimeError, match="non-CSV"):
        fetch_csv(session, "FM/D.U2.EUR.4F.KR.DFR.LEV")


def test_ingesting_twice_is_idempotent(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    session = FakeSession(load("ecb_HICP_U2.csv"))
    first = ingest_series(engine, session, SPECS["EA_HICP"], RETRIEVED)
    second = ingest_series(engine, session, SPECS["EA_HICP"], RETRIEVED)
    assert (first.inserted, first.updated) == (5, 0)
    assert (second.inserted, second.updated) == (0, 5)
