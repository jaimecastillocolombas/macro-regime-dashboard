"""News: the latest macro-relevant headlines from Finnhub, fetched live."""

import pandas as pd
import streamlit as st

from app.data import news

st.title("News")
st.caption(
    "Latest market news from Finnhub (Reuters, CNBC), filtered to central banks, rates, "
    "inflation, bonds, the economy and markets. Refreshed every 15 minutes."
)

items = news()
if items is None:
    st.info("News needs a Finnhub API key: set FINNHUB_API_KEY in .env or the app's secrets.")
    st.stop()
if items.empty:
    st.info("No macro-relevant headlines in the latest Finnhub feed.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
for row in items.itertuples():
    minutes = int((now - row.published).total_seconds() // 60)
    age = f"{minutes} min ago" if minutes < 60 else f"{minutes // 60} h ago"
    with st.container(border=True):
        st.markdown(f"**[{row.headline}]({row.url})**  \n:gray[{row.source} · {age}]")
        if row.summary:
            st.caption(row.summary)
