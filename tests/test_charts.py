"""Phone detection used to make charts static on touch screens."""

import pytest

from app.charts import is_phone


@pytest.mark.parametrize(
    ("user_agent", "phone"),
    [
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148", True),
        ("Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36", True),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36", False),
        ("", False),
    ],
)
def test_phone_user_agents(user_agent: str, phone: bool) -> None:
    assert is_phone(user_agent) is phone
