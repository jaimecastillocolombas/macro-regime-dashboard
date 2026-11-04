"""The FRED key travels in the URL: it must never reach error messages or logs."""

import logging

import pytest
import requests

from src.ingest.fred import FredRequestError, fetch_observations
from src.ingest.http import RedactSecrets, redact

KEY = "abcdef0123456789abcdef0123456789"
URL = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={KEY}&x=1"


def test_redact_masks_only_the_key() -> None:
    assert redact(URL).endswith("series_id=DGS10&api_key=***&x=1")


def test_urllib3_retry_warning_is_redacted() -> None:
    record = logging.LogRecord(
        "urllib3.connectionpool",
        logging.WARNING,
        __file__,
        0,
        "Retrying (%r) after connection broken by '%r': %s",
        ("Retry(total=3)", "Timeout", URL),
        None,
    )
    RedactSecrets().filter(record)
    assert KEY not in record.getMessage()
    assert "api_key=***" in record.getMessage()


class FailingSession:
    def get(self, url: str, params: dict, timeout: int):
        raise requests.HTTPError(f"400 Client Error: Bad Request for url: {URL}")


def test_fred_errors_do_not_carry_the_key() -> None:
    with pytest.raises(FredRequestError) as caught:
        fetch_observations(FailingSession(), "DGS10", KEY)
    assert KEY not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
