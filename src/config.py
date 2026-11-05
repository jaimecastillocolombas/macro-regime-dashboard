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
    source_key: str = ""  # the source's own identifier when it differs from series_id

    def metadata_row(self) -> dict[str, object]:
        """Row for the ``series`` table (lag_note and source_key are not stored)."""
        row = asdict(self)
        row.pop("lag_note")
        row.pop("source_key")
        return row


# Yield curves: tenor -> years to maturity, and the series holding each tenor
TENOR_YEARS: dict[str, float] = {
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1,
    "2Y": 2,
    "5Y": 5,
    "7Y": 7,
    "10Y": 10,
    "20Y": 20,
    "30Y": 30,
}
US_CURVE = {
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}
EA_CURVE = {tenor: f"EA_YC_{tenor}" for tenor in TENOR_YEARS}


def _tenor_name(tenor: str) -> str:
    """'3M' -> '3-month', '10Y' -> '10-year'."""
    return f"{tenor[:-1]}-{'month' if tenor.endswith('M') else 'year'}"


_H15 = "H.15 release: published the next business day (federalreserve.gov/releases/h15)"
_CPI = (
    "Fallback only, before ALFRED vintages exist. Measured first-release lag of US CPI "
    "from the reference month start: 39-78 days, median ~44 (ALFRED, 1985-2025)."
)

_SHARES = (
    "OECD monthly average of all listed shares. Fallback only: ALFRED gives the first release. "
    "Observed on 2026-11-05: September published, October not yet."
)

# Equity markets by country: OECD share price indices on FRED, monthly, decades of history.
# Index levels are free nowhere else (Finnhub's free plan has neither indices nor history).
SHARE_PRICE_COUNTRIES = {
    "US": "United States",
    "ES": "Spain",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "GB": "United Kingdom",
    "JP": "Japan",
}

FRED_SERIES: tuple[SeriesSpec, ...] = (
    *(
        SeriesSpec(
            sid,
            "FRED",
            f"US Treasury yield, {_tenor_name(tenor)}",
            "percent",
            "daily",
            "US",
            1,
            _H15,
        )
        for tenor, sid in US_CURVE.items()
    ),
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
    SeriesSpec(
        "VIXCLS",
        "FRED",
        "CBOE VIX, S&P 500 30-day implied volatility",
        "index points",
        "daily",
        "US",
        1,
        "Cboe close, posted on FRED the next business day",
    ),
    SeriesSpec(
        "BAA10Y",
        "FRED",
        "Moody's Baa corporate yield minus 10-year Treasury",
        "percent",
        "daily",
        "US",
        1,
        "Moody's daily yields on FRED the next business day. Chosen over ICE BofA high-yield "
        "spreads, which FRED only serves for the last 3 years.",
    ),
    *(
        SeriesSpec(
            f"SPASTT01{code}M661N",
            "FRED",
            f"Share prices, {country} (OECD, all shares)",
            "index 2015=100",
            "monthly",
            code,
            60,
            _SHARES,
        )
        for code, country in SHARE_PRICE_COUNTRIES.items()
    ),
)


_YC = "Published each TARGET business day around 12:00 CET for the previous business day"
_DFR = "Policy rates are announced before they take effect: known on their own date"
_HICP = (
    "Eurostat final release around the 17th-20th of the next month, January later because of "
    "the annual weight update; 60 days from the month start covers it."
)
_IRS = (
    "Monthly average. Observed on 2026-11-04: September published, October not yet, so the "
    "lag is 35-64 days from the month start; 60 days is conservative."
)
_CISS = (
    "Observed on 2026-11-05: latest value dated 2026-11-03, i.e. two TARGET days; three is "
    "conservative. Replaces the old SS_CI series, discontinued in 2025."
)

# 10-year government yields (ECB IRS): Germany is the benchmark for every risk premium
LONG_TERM_RATE_COUNTRIES = {
    "ES": "Spain",
    "DE": "Germany",
    "IT": "Italy",
    "FR": "France",
    "PT": "Portugal",
    "GR": "Greece",
}


def _ecb(series_id, key, name, unit, frequency, country, lag, note) -> SeriesSpec:
    return SeriesSpec(series_id, "ECB", name, unit, frequency, country, lag, note, key)


# HICP moved from the frozen ICP dataflow (last value Dec-2025) to HICP, provider 4D0.
ECB_SERIES: tuple[SeriesSpec, ...] = (
    *(
        _ecb(
            sid,
            f"YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}",
            f"Euro area AAA yield, {_tenor_name(tenor)}",
            "percent",
            "daily",
            "EA",
            1,
            _YC,
        )
        for tenor, sid in EA_CURVE.items()
    ),
    _ecb(
        "EA_DFR",
        "FM/D.U2.EUR.4F.KR.DFR.LEV",
        "ECB deposit facility rate",
        "percent",
        "daily",
        "EA",
        0,
        _DFR,
    ),
    _ecb(
        "EA_HICP",
        "HICP/M.U2.N.000000.4D0.ANR",
        "Euro area HICP, all items",
        "percent y/y",
        "monthly",
        "EA",
        60,
        _HICP,
    ),
    _ecb(
        "EA_HICP_CORE",
        "HICP/M.U2.N.XEF000.4D0.ANR",
        "Euro area HICP excl. energy, food, alcohol and tobacco",
        "percent y/y",
        "monthly",
        "EA",
        60,
        _HICP,
    ),
    _ecb(
        "ES_HICP",
        "HICP/M.ES.N.000000.4D0.ANR",
        "Spain HICP, all items",
        "percent y/y",
        "monthly",
        "ES",
        60,
        _HICP,
    ),
    *(
        _ecb(
            f"{code}_LTR_10Y",
            f"IRS/M.{code}.L.L40.CI.0000.EUR.N.Z",
            f"{country} 10-year government bond yield",
            "percent",
            "monthly",
            code,
            60,
            _IRS,
        )
        for code, country in LONG_TERM_RATE_COUNTRIES.items()
    ),
    _ecb(
        "EA_CISS",
        "CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX",
        "ECB Composite Indicator of Systemic Stress, euro area",
        "index 0-1",
        "daily",
        "EA",
        3,
        _CISS,
    ),
)


_INE_CPI = (
    "INE final CPI release around the 12th-15th of the next month (its month-end flash is "
    "captured by the download-day cap); 50 days from the month start is conservative."
)

# Base 2025 series (classification 120). The base 2021 codes (IPC251856...) stop at Dec-2025.
INE_SERIES: tuple[SeriesSpec, ...] = (
    SeriesSpec(
        "ES_CPI",
        "INE",
        "Spain CPI, all items",
        "percent y/y",
        "monthly",
        "ES",
        50,
        _INE_CPI,
        "IPC290750",
    ),
    SeriesSpec(
        "ES_CPI_CORE",
        "INE",
        "Spain core CPI (excl. unprocessed food and energy)",
        "percent y/y",
        "monthly",
        "ES",
        50,
        _INE_CPI,
        "IPC292510",
    ),
)
