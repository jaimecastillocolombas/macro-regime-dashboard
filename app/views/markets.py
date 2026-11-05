"""Markets: equity performance by country from the OECD share price indices."""

import pandas as pd
import streamlit as st

from app.charts import color, line_figure
from app.data import load
from src.config import SHARE_PRICE_COUNTRIES
from src.transform.series import rebase

YEARS = 5  # the chart compares growth over the last five years

stored = load(tuple(f"SPASTT01{code}M661N" for code in SHARE_PRICE_COUNTRIES))
indices = {
    country: stored[f"SPASTT01{code}M661N"]["value"]
    for code, country in SHARE_PRICE_COUNTRIES.items()
}

latest = min(values.index[-1] for values in indices.values())

st.title("Markets")
st.subheader(f"Stock markets by country: change in the year to {latest:%B %Y}")

for column, (country, values) in zip(st.columns(len(indices)), indices.items(), strict=True):
    change = (values.iloc[-1] / values.iloc[-13] - 1) * 100
    with column:
        st.metric(country, f"{change:+.1f}%")

start = latest - pd.DateOffset(years=YEARS)
st.subheader(f"Growth since {start:%B %Y} (= 100)")
lines = {country: rebase(values, start) for country, values in indices.items()}
figure = line_figure(
    lines,
    "Index, start = 100",
    reference=100.0,
    colors={country: color(slot) for slot, country in enumerate(lines, start=1)},
    height=440,
)
st.plotly_chart(figure, width="stretch")
st.caption(
    "OECD share price indices for all listed shares, monthly averages, in local currency and "
    "without dividends. Source: OECD via FRED. Dotted line: the starting level."
)
