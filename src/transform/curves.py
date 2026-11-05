"""Pure helpers for yield curves and spread regimes."""

import pandas as pd

from src.config import TENOR_YEARS


def curve_on(
    stored: dict[str, pd.DataFrame], curve: dict[str, str], when: pd.Timestamp
) -> pd.DataFrame:
    """The curve as it stood on ``when``: each tenor's last value dated on or before it.

    Returns one row per tenor (tenor, years, value, date), shortest maturity first. A tenor with
    no data yet (e.g. 30Y before 1977) is left out rather than filled.
    """
    rows = []
    for tenor, series_id in curve.items():
        values = stored[series_id]["value"].loc[:when]
        if not values.empty:
            rows.append((tenor, TENOR_YEARS[tenor], values.iloc[-1], values.index[-1]))
    return pd.DataFrame(rows, columns=["tenor", "years", "value", "date"])


def runs_below(
    values: pd.Series, threshold: float = 0.0
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """(first, last) dates of each uninterrupted run of observations below ``threshold``."""
    below = values < threshold
    run_id = (below != below.shift()).cumsum()
    return [(run.index[0], run.index[-1]) for _, run in values[below].groupby(run_id[below])]
