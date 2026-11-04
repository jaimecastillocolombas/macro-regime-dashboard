"""Shared HTTP session: every request gets a timeout and retries with exponential backoff.

API keys that travel in the query string (FRED) are redacted from urllib3's retry warnings, so
they never reach the logs of the scheduled workflow.
"""

import logging
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT = 30  # seconds

_SECRET_VALUE = re.compile(r"(?<=api_key=)[^&\s'\"]+")  # the value right after "api_key="


def redact(text: str) -> str:
    """Mask the value of any ``api_key=`` query parameter."""
    return _SECRET_VALUE.sub("***", text)


class RedactSecrets(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


# urllib3 logs the full URL, query string included, every time it retries
logging.getLogger("urllib3.connectionpool").addFilter(RedactSecrets())


def make_session(retries: int = 4, backoff: float = 1.0) -> requests.Session:
    """Session that retries connection errors, 429 and 5xx (waits 1s, 2s, 4s, 8s by default).

    4xx other than 429 are not retried: a bad series id or key will not fix itself.
    """
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "macro-regime-dashboard (portfolio project)"
    return session
