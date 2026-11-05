"""Freshness header: what each source reaches and when it goes stale."""

import pandas as pd

from app.header import freshness_line

T = pd.Timestamp
NOW = T("2026-11-05 09:00", tz="UTC")


def status(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["source", "frequency", "retrieved_at", "latest_date"])
    frame["retrieved_at"] = pd.to_datetime(frame["retrieved_at"], utc=True)
    frame["latest_date"] = pd.to_datetime(frame["latest_date"])
    return frame


def test_daily_and_monthly_reach_are_shown_separately() -> None:
    line = freshness_line(
        status(
            [
                ("FRED", "daily", "2026-11-05 08:12", "2026-11-04"),
                ("FRED", "monthly", "2026-11-05 08:10", "2026-09-01"),
            ]
        ),
        NOW,
    )
    assert "**FRED** daily to 4 Nov 2026, monthly to Sep 2026" in line
    assert "checked 5 Nov 08:12 UTC" in line
    assert "warning" not in line


def test_a_source_not_downloaded_for_two_days_is_flagged() -> None:
    line = freshness_line(
        status(
            [
                ("ECB", "daily", "2026-11-03 06:00", "2026-11-02"),
                ("INE", "monthly", "2026-11-05 08:14", "2026-10-01"),
            ]
        ),
        NOW,
    )
    ecb, ine = line.split("|")
    assert ":material/warning:" in ecb and "not updated for 2 days" in ecb
    assert "warning" not in ine
