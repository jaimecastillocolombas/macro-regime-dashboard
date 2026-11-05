"""Pure functions on single series.

A series is a DataFrame indexed by reference ``date`` with two columns: ``value`` and
``available_at``. A derived value is public only once every input it needs is public, so its
``available_at`` is the latest of its inputs'. Because of that, filtering a derived series by
``available_at <= t`` gives the same result as deriving it from inputs filtered at ``t``.
"""

import pandas as pd

COLUMNS = ["value", "available_at"]


def from_long(frame: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """One series out of the long frame returned by ``db.read_observations``."""
    one = frame.loc[frame["series_id"] == series_id, ["date", *COLUMNS]]
    return one.set_index("date").sort_index()


def spread(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """``a - b`` on the dates both series have."""
    both = a.merge(b, how="inner", left_index=True, right_index=True, suffixes=("_a", "_b"))
    return pd.DataFrame(
        {
            "value": both["value_a"] - both["value_b"],
            "available_at": both[["available_at_a", "available_at_b"]].max(axis=1),
        }
    )


def yoy(index: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    """Percent change of an index over ``months``, matched by date rather than by position.

    A missing month yields no value instead of silently comparing the wrong months.
    """
    previous = index.reindex(index.index - pd.DateOffset(months=months))
    previous.index = index.index
    result = pd.DataFrame(
        {
            "value": (index["value"] / previous["value"] - 1) * 100,
            "available_at": pd.concat(
                [index["available_at"], previous["available_at"]], axis=1
            ).max(axis=1, skipna=False),
        }
    )
    return result.dropna()


def as_of(series: pd.DataFrame, when: pd.Timestamp) -> pd.DataFrame:
    """What was public on ``when``."""
    return series[series["available_at"] <= when]


def trailing(values: pd.Series, years: int | None) -> pd.Series:
    """The last ``years`` years up to the latest observation; everything when ``years`` is None."""
    if years is None or values.empty:
        return values
    return values.loc[values.index[-1] - pd.DateOffset(years=years) :]


def percentile_rank(values: pd.Series) -> float:
    """Where the latest value sits in the series' own history: the percent of observations at
    or below it (100 = the highest reading on record)."""
    return float((values <= values.iloc[-1]).mean() * 100)


def rebase(values: pd.Series, start: pd.Timestamp, base: float = 100.0) -> pd.Series:
    """The series from ``start`` on, scaled so its first value equals ``base``. Puts indices
    with different levels on one chart: each line then reads as growth since ``start``."""
    since = values.loc[start:]
    return since / since.iloc[0] * base
