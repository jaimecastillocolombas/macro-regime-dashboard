"""Header line telling how fresh each source is (pure: no Streamlit calls)."""

import pandas as pd

STALE_AFTER = pd.Timedelta(hours=36)  # ingestion runs daily: more than a day and a half is a miss


def freshness_line(status: pd.DataFrame, now: pd.Timestamp) -> str:
    """One entry per source: how recent its daily and monthly data are, and when it was last
    downloaded. A source not downloaded for longer than STALE_AFTER is flagged."""
    parts = []
    for source, rows in status.groupby("source", sort=True):
        latest = {row.frequency: row.latest_date for row in rows.itertuples()}
        reach = ", ".join(
            f"daily to {date.day} {date:%b %Y}"
            if frequency == "daily"
            else f"monthly to {date:%b %Y}"
            for frequency, date in sorted(latest.items())
        )
        checked = rows["retrieved_at"].max()
        text = f"**{source}** {reach} · checked {checked.day} {checked:%b %H:%M} UTC"
        age = now - checked
        if age > STALE_AFTER:
            text = f":orange[:material/warning: {text}, not updated for {age.days} days]"
        parts.append(text)
    return "  |  ".join(parts)
