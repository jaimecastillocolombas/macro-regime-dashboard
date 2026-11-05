"""Yield-curve helper tests on hand-made series."""

import pandas as pd

from src.transform.curves import curve_on, runs_below

T = pd.Timestamp


def daily(points: dict[str, float]) -> pd.DataFrame:
    index = pd.DatetimeIndex([T(d) for d in points])
    return pd.DataFrame({"value": list(points.values()), "available_at": index}, index=index)


def test_curve_takes_each_tenors_last_value_on_or_before_the_date() -> None:
    stored = {
        "S3M": daily({"2026-10-02": 3.9, "2026-10-05": 3.8}),
        "S10Y": daily({"2026-10-02": 4.5}),  # no value on the 5th: falls back to the 2nd
        "S30Y": daily({"2026-10-06": 4.9}),  # only after the date: left out
    }
    curve = curve_on(stored, {"3M": "S3M", "10Y": "S10Y", "30Y": "S30Y"}, T("2026-10-05"))
    assert list(curve["tenor"]) == ["3M", "10Y"]
    assert list(curve["value"]) == [3.8, 4.5]
    assert list(curve["years"]) == [0.25, 10]
    assert curve.loc[1, "date"] == T("2026-10-02")


def test_runs_below_zero() -> None:
    spread = daily(
        {
            "2026-01-01": 0.2,
            "2026-01-02": -0.1,
            "2026-01-03": -0.3,
            "2026-01-04": 0.1,
            "2026-01-05": -0.2,
        }
    )["value"]
    assert runs_below(spread) == [
        (T("2026-01-02"), T("2026-01-03")),
        (T("2026-01-05"), T("2026-01-05")),
    ]


def test_no_runs_when_never_below() -> None:
    assert runs_below(daily({"2026-01-01": 0.5})["value"]) == []
