"""Rates & Bonds: yield curves, curve slope with inversions, Spain-Germany risk premium."""

import pandas as pd
import streamlit as st

from app.charts import color, curve_figure, line_figure
from app.data import load
from src.config import EA_CURVE, US_CURVE
from src.transform.curves import curve_on, runs_below
from src.transform.series import spread

MARKETS = {"United States": US_CURVE, "Euro area (AAA)": EA_CURVE}
SLOPE_SINCE = pd.Timestamp("2004-09-06")  # first euro curve date: both slope charts start here

stored = load(tuple(sorted({*US_CURVE.values(), *EA_CURVE.values(), "ES_LTR_10Y", "DE_LTR_10Y"})))

st.title("Rates & Bonds")

# ----------------------------------------------------------------------------- yield curves

st.subheader("Yield curves")
for column, (market, curve) in zip(st.columns(2), MARKETS.items(), strict=True):
    today = stored[curve["10Y"]].index[-1]
    lines = [
        (f"{today.day} {today:%b %Y}", today, color(1)),
        ("1 month earlier", today - pd.DateOffset(months=1), color(2)),
        ("1 year earlier", today - pd.DateOffset(years=1), color(3)),
    ]
    with column:
        st.markdown(f"**{market}**")
        figure = curve_figure([(label, curve_on(stored, curve, day), c) for label, day, c in lines])
        st.plotly_chart(figure, width="stretch")

# ----------------------------------------------------------------------------- slope

st.subheader("Curve slope: 10-year minus 2-year")
st.caption("Shaded: inverted curve (10Y below 2Y), a classic recession warning.")
for column, (market, curve) in zip(st.columns(2), MARKETS.items(), strict=True):
    slope = spread(stored[curve["10Y"]], stored[curve["2Y"]])["value"].loc[SLOPE_SINCE:]
    with column:
        st.markdown(f"**{market}**")
        figure = line_figure({market: slope}, "Percentage points", shaded=runs_below(slope))
        st.plotly_chart(figure, width="stretch")

# ----------------------------------------------------------------------------- risk premium

st.subheader("Spain-Germany risk premium")
premium = spread(stored["ES_LTR_10Y"], stored["DE_LTR_10Y"])["value"] * 100
metric, chart = st.columns([1, 4])
with metric:
    st.metric(
        f"{premium.index[-1]:%B %Y}",
        f"{premium.iloc[-1]:.0f} bp",
        f"{premium.iloc[-1] - premium.iloc[-13]:+.0f} bp in a year",
        delta_color="inverse",
    )
with chart:
    st.plotly_chart(line_figure({"ES-DE": premium}, "Basis points"), width="stretch")
st.caption("10-year yield gap, monthly averages. Source: ECB long-term rates (IRS).")
