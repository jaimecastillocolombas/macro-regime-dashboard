"""Transformation tests on small hand-made series (no database, no network)."""

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from src.config import FRED_SERIES
from src.db import get_engine, read_observations, upsert_observations, upsert_series
from src.transform.derived import build, required_inputs
from src.transform.series import as_of, from_long, percentile_rank, spread, trailing, yoy

T = pd.Timestamp


def series(points: dict[str, tuple[float, str]]) -> pd.DataFrame:
    """{date: (value, available_at)} -> series frame."""
    frame = pd.DataFrame(
        [(T(d), v, T(a)) for d, (v, a) in points.items()],
        columns=["date", "value", "available_at"],
    )
    return frame.set_index("date")


def test_spread_is_available_when_its_latest_input_is() -> None:
    es = series({"2026-08-01": (3.6, "2026-09-30"), "2026-09-01": (3.9, "2026-10-31")})
    de = series({"2026-08-01": (3.2, "2026-10-02"), "2026-09-01": (3.5, "2026-10-30")})
    result = spread(es, de)
    assert result.loc[T("2026-08-01"), "value"] == pytest.approx(0.4)
    assert result.loc[T("2026-08-01"), "available_at"] == T("2026-10-02")  # Germany came later
    assert result.loc[T("2026-09-01"), "available_at"] == T("2026-10-31")


def test_spread_only_on_common_dates() -> None:
    a = series({"2026-11-02": (3.0, "2026-11-03"), "2026-11-03": (3.1, "2026-11-04")})
    b = series({"2026-11-03": (2.0, "2026-11-04")})
    assert list(spread(a, b).index) == [T("2026-11-03")]


def test_yoy_value_and_availability() -> None:
    index = series({"2025-09-01": (100.0, "2025-10-15"), "2026-09-01": (103.0, "2026-10-14")})
    result = yoy(index)
    assert result.loc[T("2026-09-01"), "value"] == pytest.approx(3.0)
    assert result.loc[T("2026-09-01"), "available_at"] == T("2026-10-14")
    assert len(result) == 1  # Sep-2025 has no year-earlier value


def test_yoy_matches_by_date_not_by_position() -> None:
    """With a missing month, shifting 12 rows would compare the wrong months."""
    points = {f"2025-{m:02d}-01": (100.0 + m, f"2025-{m:02d}-28") for m in range(1, 13)}
    points |= {f"2026-{m:02d}-01": (200.0, f"2026-{m:02d}-28") for m in (1, 3)}  # Feb missing
    del points["2025-03-01"]  # and March 2025 too
    result = yoy(series(points))
    assert list(result.index) == [T("2026-01-01")]  # March 2026 has no March 2025 to compare


def test_as_of_hides_what_was_not_yet_public() -> None:
    s = series({"2026-09-01": (4.9, "2026-10-14"), "2026-10-01": (4.9, "2026-11-04")})
    assert list(as_of(s, T("2026-11-01")).index) == [T("2026-09-01")]


def test_catalogue_builds_from_stored_series() -> None:
    stored = {
        "CPIAUCNS": series(
            {"2025-09-01": (100.0, "2025-10-15"), "2026-09-01": (102.0, "2026-10-14")}
        ),
        "ES_LTR_10Y": series({"2026-09-01": (3.927, "2026-10-31")}),
        "DE_LTR_10Y": series({"2026-09-01": (3.473, "2026-10-31")}),
    }
    out = build(stored, ["US_CPI_YOY", "ES_DE_SPREAD"])
    assert out["US_CPI_YOY"]["value"].iloc[0] == pytest.approx(2.0)
    assert out["ES_DE_SPREAD"]["value"].iloc[0] == pytest.approx(0.454)
    assert required_inputs(["ES_DE_SPREAD"]) == {"ES_LTR_10Y", "DE_LTR_10Y"}


def test_read_observations_point_in_time(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    spec = next(s for s in FRED_SERIES if s.series_id == "CPILFENS")
    upsert_series(engine, [spec.metadata_row()])
    retrieved = datetime(2026, 11, 4, tzinfo=UTC)
    upsert_observations(
        engine,
        [
            {
                "series_id": "CPILFENS",
                "date": date(2026, 8, 1),
                "value": 338.0,
                "available_at": date(2026, 9, 11),
                "retrieved_at": retrieved,
            },
            {
                "series_id": "CPILFENS",
                "date": date(2026, 9, 1),
                "value": 339.3,
                "available_at": date(2026, 10, 14),
                "retrieved_at": retrieved,
            },
        ],
    )
    everything = from_long(read_observations(engine, ["CPILFENS"]), "CPILFENS")
    before_release = read_observations(engine, ["CPILFENS"], as_of=date(2026, 10, 13))
    assert len(everything) == 2
    assert list(before_release["date"]) == [T("2026-08-01")]
    assert everything["available_at"].dtype.kind == "M"


def test_trailing_keeps_the_last_years() -> None:
    values = pd.Series(1.0, index=pd.date_range("2016-01-01", "2026-10-01", freq="MS"))
    assert trailing(values, 5).index[0] == T("2021-10-01")
    assert trailing(values, None).equals(values)


def test_percentile_rank_of_the_latest_value() -> None:
    history = pd.Series([10.0, 20.0, 30.0, 40.0, 25.0])
    assert percentile_rank(history) == pytest.approx(60)  # 10, 20, 25 of 5 are <= 25
    assert percentile_rank(pd.Series([1.0, 2.0, 3.0])) == pytest.approx(100)
