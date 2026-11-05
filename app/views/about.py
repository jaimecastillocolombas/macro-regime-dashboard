"""About: what the dashboard is, how the data stays point-in-time, and where it comes from.

The examples and the source table are read from the database and the series catalogue, so the
page cannot drift from what the pipeline actually does.
"""

import pandas as pd
import streamlit as st

from app.data import load
from app.style import cards_on_canvas
from src.config import ALL_SERIES, lag_groups

REPO = "https://github.com/jaimecastillocolombas/macro-regime-dashboard"
# One monthly series per source plus a daily one, to show what "available" means in practice
EXAMPLES = {
    "CPIAUCNS": "US CPI (FRED/ALFRED)",
    "EA_HICP": "Euro area HICP (ECB)",
    "ES_CPI": "Spain CPI (INE)",
    "DGS10": "US 10-year Treasury yield (FRED)",
}

cards_on_canvas()


def card(key: str, title: str, body: str) -> None:
    with st.container(border=True, key=f"card-about-{key}"):
        st.markdown(f"**{title}**")
        st.markdown(body)


def latest_release(frame: pd.DataFrame, frequency: str) -> dict[str, str]:
    """The newest observation: the period it refers to, the day it became public and how long
    after the end of that period."""
    period, public = frame.index[-1], frame["available_at"].iloc[-1]
    if frequency == "monthly":
        label, period_end = f"{period:%b %Y}", period + pd.offsets.MonthEnd(0)
    else:
        label, period_end = f"{period.day} {period:%b %Y}", period
    return {
        "Refers to": label,
        "Public on": f"{public.day} {public:%b %Y}",
        "Days after the period ended": str((public - period_end).days),
    }


st.title("About")
st.markdown(
    "A self-updating macro dashboard for rates, bonds, inflation, risk and markets in the US, "
    "the euro area and Spain. Every night a pipeline collects the data from the Federal "
    "Reserve, the ECB and Spain's INE and stores **when each value became public** next to "
    "what it says. That point-in-time record is what will let the regime-rotation strategy "
    "of the next phase be backtested without look-ahead bias."
)

# ----------------------------------------------------------------------------- pipeline

collect, store, show = st.columns(3)
with collect:
    card(
        "collect",
        "1 · Collect",
        "A GitHub Actions job runs daily at 22:30 UTC, after the ECB publishes. Each source "
        "has its own client with timeouts and retries; one failing series never stops the "
        "rest, and the run ends with a summary.",
    )
with store:
    card(
        "store",
        "2 · Store",
        "Two tables in Postgres: series metadata and observations "
        "(`date`, `value`, `available_at`, `retrieved_at`). Writes are an idempotent upsert, "
        "so running the job twice changes nothing.",
    )
with show:
    card(
        "show",
        "3 · Show",
        "This Streamlit app only reads, caches and plots. Spreads and year-on-year rates are "
        "computed on read by small, tested functions, never stored.",
    )

# ----------------------------------------------------------------------------- point in time

st.subheader("Why `available_at` matters")
st.markdown(
    "Macro data is published with a delay and later revised. A backtest that uses September's "
    "inflation on 30 September is using information nobody had yet. So every observation "
    "carries the day it became public, and every signal will only see data with "
    "`available_at` on or before the day it trades. The latest values in the database:"
)
frequencies = {spec.series_id: spec.frequency for spec in ALL_SERIES}
stored = load(tuple(EXAMPLES))
examples = pd.DataFrame(
    [
        {"Series": name, **latest_release(stored[sid], frequencies[sid])}
        for sid, name in EXAMPLES.items()
        if not stored[sid].empty
    ]
)
st.dataframe(examples, hide_index=True, width="stretch")
st.caption(
    "US CPI uses its real first-release date from ALFRED's vintage history. The ECB and INE "
    "keep no release history, so their values get a documented, conservative lag, capped by "
    "the day the pipeline first saw them. Daily yields move by one business day of the "
    "publisher's calendar (US federal holidays, TARGET2)."
)

# ----------------------------------------------------------------------------- sources

st.subheader("Sources and publication lags")
table = pd.DataFrame(lag_groups(ALL_SERIES)).rename(
    columns={
        "source": "Source",
        "series": "Series",
        "frequency": "Frequency",
        "lag_days": "Lag (days)",
        "rule": "How the lag is set",
    }
)
# A static table, not st.dataframe: the rules are sentences and need to wrap
st.table(table.drop(columns="count").set_index("Source"))
st.caption(
    f"{len(ALL_SERIES)} series. Lags are business days for daily series and calendar days "
    "from the start of the month for monthly ones. News comes live from Finnhub and is not "
    "stored."
)

# ----------------------------------------------------------------------------- engineering

st.subheader("Engineering")
st.markdown(
    "- **Tests** run on saved API responses, never on the live APIs, and CI runs ruff and "
    "pytest on every push.\n"
    "- **Not seasonally adjusted US CPI**: 88-91% of the seasonally adjusted history has been "
    "revised since first release, so the NSA series keeps the backtest honest.\n"
    "- **Secrets** never reach the code, the logs or git; the app connects as a database role "
    "that can only use its own schema.\n"
    "- **Stack**: Python 3.11, pandas, SQLAlchemy, Postgres (Supabase), Streamlit, Plotly, "
    "GitHub Actions, pytest, ruff."
)
st.markdown(f"Code, tests and design notes: [{REPO.removeprefix('https://')}]({REPO})")
