"""Streamlit entry point: ``streamlit run app/streamlit_app.py``."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit only puts app/ on the import path; the shared code lives in src/ at the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# On a code update Streamlit (and Streamlit Cloud) reruns this script in the same process but
# only reloads changed modules it considers part of the app, so edits to src/ were ignored
# until a reboot. Dropping our own modules makes every run import the current code. Cached
# data survives: st.cache_* keys on each function's name and source, not on the module object.
for name in [m for m in sys.modules if m.split(".")[0] in {"src", "app"}]:
    del sys.modules[name]

from app.data import source_freshness  # noqa: E402  (needs the path set above)
from app.header import freshness_line, freshness_short  # noqa: E402

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

PAGES = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/rates.py", title="Rates & Bonds"),
    st.Page("views/inflation.py", title="Inflation"),
    st.Page("views/markets.py", title="Markets"),
    st.Page("views/risk.py", title="Risk"),
    st.Page("views/news.py", title="News"),
]
# A bar across the top frees the sidebar's width for the charts. On narrow screens Streamlit
# swaps it for a sidebar hidden behind a small arrow, so phones get their own row of links
# instead (see PHONE_CSS)
navigation = st.navigation(PAGES, position="top")

# Phone layout, applied to every page. "Phone" means Streamlit has dropped its top bar, so the
# own row of links appears exactly when the bar is gone. Elsewhere only the width matters.
PHONE_CSS = (
    "<style>"
    # Each row is hidden through the wrapper Streamlit puts around it: hiding only the row
    # leaves an empty wrapper that still takes a gap (and pushes the overview past one screen)
    "[data-testid='stLayoutWrapper']:has(> .st-key-phone-nav),"
    " [data-testid='stLayoutWrapper']:has(> .st-key-freshness-short) {display: none}"
    "body:not(:has([data-testid='stTopNav']))"
    " [data-testid='stLayoutWrapper']:has(> .st-key-phone-nav) {display: flex}"
    "body:not(:has([data-testid='stTopNav'])) [data-testid='stExpandSidebarButton']"
    " {display: none}"
    "@media (max-width: 640px) {"
    # one short freshness line instead of five
    " [data-testid='stLayoutWrapper']:has(> .st-key-freshness) {display: none}"
    " [data-testid='stLayoutWrapper']:has(> .st-key-freshness-short) {display: flex}"
    # headings sized for a phone, not a monitor
    " h1 {font-size: 1.6rem !important} h2 {font-size: 1.2rem !important}"
    " h3 {font-size: 1.05rem !important}"
    # key figures two per row (Streamlit stacks every column full width), with smaller
    # values and labels that wrap instead of ending in an ellipsis; columns that also hold
    # a chart keep the full width
    " [data-testid='stColumn']:has([data-testid='stMetric'])"
    ":not(:has([data-testid='stPlotlyChart'])) {min-width: calc(50% - 8px)}"
    " [data-testid='stMetricValue'] {font-size: 1.4rem}"
    " [data-testid='stMetricLabel'] *, [data-testid='stMetricDelta'] *"
    " {white-space: normal !important; text-overflow: clip}"
    "}"
    # no Plotly toolbar on touch screens, where it stays visible over the legends
    "@media (hover: none) {.modebar-container {display: none}}"
    "</style>"
)


status = source_freshness()
if status.empty:
    # Without data every page would fail with an obscure IndexError; say what is wrong instead
    st.error(
        "The database is empty or unreachable. Locally, run `python -m src.ingest.run`; "
        "on Streamlit Cloud, check the DATABASE_URL secret."
    )
    st.stop()
st.html(PHONE_CSS)
with st.container(key="phone-nav", horizontal=True, gap="xxsmall"):
    for page in PAGES:
        st.page_link(page, width="content")
now = pd.Timestamp.now(tz="UTC")
st.container(key="freshness").caption(freshness_line(status, now))
st.container(key="freshness-short").caption(freshness_short(status, now))
navigation.run()
