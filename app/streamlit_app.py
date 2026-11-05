"""Streamlit entry point: ``streamlit run app/streamlit_app.py``."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit only puts app/ on the import path; the shared code lives in src/ at the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data import source_freshness  # noqa: E402  (needs the path set above)
from app.header import freshness_line  # noqa: E402

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

navigation = st.navigation(
    [
        st.Page("views/rates.py", title="Rates & Bonds", default=True),
        st.Page("views/inflation.py", title="Inflation"),
    ]
)


status = source_freshness()
if status.empty:
    # Without data every page would fail with an obscure IndexError; say what is wrong instead
    st.error(
        "The database is empty or unreachable. Locally, run `python -m src.ingest.run`; "
        "on Streamlit Cloud, check the DATABASE_URL secret."
    )
    st.stop()
st.caption(freshness_line(status, pd.Timestamp.now(tz="UTC")))
navigation.run()
