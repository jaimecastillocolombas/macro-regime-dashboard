"""Runtime configuration and the catalogue of series we ingest.

Every series documents its publication lag, because ``available_at`` (when a value became
public) must never be confused with ``date`` (the period the value refers to).
"""

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # explicit path: find_dotenv() breaks when run from stdin/notebooks

DEFAULT_DATABASE_URL = f"sqlite:///{(ROOT / 'data' / 'macro.db').as_posix()}"


def database_url() -> str:
    """Database URL from the environment; a SQLite file under data/ by default."""
    return os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def fred_api_key() -> str:
    key = os.getenv("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY is not set (see .env.example)")
    return key


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    source: str
    name: str
    unit: str
    frequency: str  # "daily" | "monthly"
    country: str
    publication_lag_days: int  # business days for daily series, calendar days for monthly
    lag_note: str  # where the lag comes from

    def metadata_row(self) -> dict[str, object]:
        """Row for the ``series`` table (lag_note is documentation, not stored)."""
        row = asdict(self)
        row.pop("lag_note")
        return row


_H15 = "H.15 release: published the next business day (federalreserve.gov/releases/h15)"
_CPI = (
    "Fallback only, before ALFRED vintages exist. Measured first-release lag of US CPI "
    "from the reference month start: 39-78 days, median ~44 (ALFRED, 1985-2025)."
)

FRED_SERIES: tuple[SeriesSpec, ...] = (
    SeriesSpec("DGS3MO", "FRED", "US Treasury yield, 3-month", "percent", "daily", "US", 1, _H15),
    SeriesSpec("DGS2", "FRED", "US Treasury yield, 2-year", "percent", "daily", "US", 1, _H15),
    SeriesSpec("DGS10", "FRED", "US Treasury yield, 10-year", "percent", "daily", "US", 1, _H15),
    SeriesSpec("T10Y2Y", "FRED", "US 10Y minus 2Y spread", "percent", "daily", "US", 1, _H15),
    SeriesSpec("T10Y3M", "FRED", "US 10Y minus 3M spread", "percent", "daily", "US", 1, _H15),
    SeriesSpec(
        "T5YIFR",
        "FRED",
        "US 5y5y forward inflation expectation",
        "percent",
        "daily",
        "US",
        1,
        "Derived from H.15 nominal and TIPS yields: next business day",
    ),
    SeriesSpec(
        "CPIAUCNS", "FRED", "US CPI, all items, NSA", "index 1982-84=100", "monthly", "US", 60, _CPI
    ),
    SeriesSpec(
        "CPILFENS",
        "FRED",
        "US CPI, less food and energy, NSA",
        "index 1982-84=100",
        "monthly",
        "US",
        60,
        _CPI,
    ),
)
