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
from app.header import freshness_line  # noqa: E402

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

navigation = st.navigation(
    [
        st.Page("views/overview.py", title="Overview", default=True),
        st.Page("views/rates.py", title="Rates & Bonds"),
        st.Page("views/inflation.py", title="Inflation"),
        st.Page("views/markets.py", title="Markets"),
        st.Page("views/risk.py", title="Risk"),
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
