"""Streamlit entry point: ``streamlit run app/streamlit_app.py``."""

import sys
from pathlib import Path

import streamlit as st

# Streamlit only puts app/ on the import path; the shared code lives in src/ at the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

navigation = st.navigation(
    [
        st.Page("views/rates.py", title="Rates & Bonds", default=True),
        st.Page("views/inflation.py", title="Inflation"),
    ]
)
navigation.run()
