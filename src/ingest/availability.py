"""When did each observation become public? Shared by every source.

Daily series move by business days of the publisher's calendar; monthly series move by
calendar days. An observation is never marked available before its own reference date.
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    EasterMonday,
    GoodFriday,
    Holiday,
    USFederalHolidayCalendar,
)

from src.config import SeriesSpec


class TargetHolidayCalendar(AbstractHolidayCalendar):
    """TARGET2 closing days: the ECB publishes nothing on them."""

    rules = [
        Holiday("New Year's Day", month=1, day=1),
        GoodFriday,
        EasterMonday,
        Holiday("Labour Day", month=5, day=1),
        Holiday("Christmas Day", month=12, day=25),
        Holiday("Boxing Day", month=12, day=26),
    ]


HOLIDAY_CALENDARS: dict[str, type[AbstractHolidayCalendar]] = {
    "FRED": USFederalHolidayCalendar,
    "ECB": TargetHolidayCalendar,
}


def add_business_days(
    dates: pd.DatetimeIndex, n: int, calendar: AbstractHolidayCalendar
) -> pd.DatetimeIndex:
    """Vectorised ``dates + n`` business days, skipping weekends and the calendar's holidays."""
    if dates.empty:
        return dates
    holidays = calendar.holidays(dates.min(), dates.max() + pd.Timedelta(days=30))
    shifted = np.busday_offset(
        dates.values.astype("datetime64[D]"),
        n,
        roll="forward",
        holidays=holidays.values.astype("datetime64[D]"),
    )
    return pd.DatetimeIndex(shifted)


def available_at_with_lag(dates: pd.DatetimeIndex, spec: SeriesSpec) -> pd.Series:
    """Conservative availability from the series' fixed publication lag."""
    if spec.frequency == "daily":
        calendar = HOLIDAY_CALENDARS[spec.source]()
        shifted = add_business_days(dates, spec.publication_lag_days, calendar)
    else:
        shifted = dates + pd.Timedelta(days=spec.publication_lag_days)
    return pd.Series(shifted, index=dates, name="available_at")


def build_rows(
    spec: SeriesSpec,
    values: pd.Series,
    retrieved_at: datetime,
    first_release: pd.Series | None = None,
) -> list[dict[str, Any]]:
    """Rows for the ``observations`` table.

    Where a first-release date exists it wins; otherwise the lag rule applies. An observation is
    never marked available before its own reference date.
    """
    available = available_at_with_lag(values.index, spec)
    if first_release is not None:
        known = first_release.reindex(values.index).dropna()
        available.loc[known.index] = known
    available = available.where(available >= values.index, values.index)
    return [
        {
            "series_id": spec.series_id,
            "date": ref.date(),
            "value": float(values[ref]),
            "available_at": available[ref].date(),
            "retrieved_at": retrieved_at,
        }
        for ref in values.index
    ]
