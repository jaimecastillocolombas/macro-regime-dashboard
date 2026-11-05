"""The series catalogue as summarised on the About page."""

from src.config import ALL_SERIES, US_CURVE, lag_groups


def test_every_series_is_counted_once() -> None:
    assert sum(row["count"] for row in lag_groups(ALL_SERIES)) == len(ALL_SERIES)


def test_the_treasury_curve_is_one_row() -> None:
    rows = [r for r in lag_groups(ALL_SERIES) if r["series"].startswith("US Treasury yield")]
    assert len(rows) == 1
    # T10Y2Y and T10Y3M share the H.15 rule, so they sit in the same row as the nine tenors
    assert rows[0]["count"] == len(US_CURVE) + 2
    assert rows[0]["series"].endswith(f"and {rows[0]['count'] - 1} more")


def test_series_ids_are_unique() -> None:
    ids = [spec.series_id for spec in ALL_SERIES]
    assert len(ids) == len(set(ids))
