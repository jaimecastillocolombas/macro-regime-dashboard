"""Rates & Bonds: yield curves, curve spreads with inversions, Spain-Germany risk premium."""

import pandas as pd
import streamlit as st

from app.charts import curve_figure, line_figure, range_control
from app.data import load
from src.config import EA_CURVE, US_CURVE
from src.transform.curves import curve_on, runs_below
from src.transform.derived import build
from src.transform.series import trailing

CURVES = {"United States (Treasuries)": US_CURVE, "Euro area (AAA)": EA_CURVE}
SPREADS = ("T10Y2Y", "T10Y3M")
PREMIUM = ("ES_LTR_10Y", "DE_LTR_10Y")

stored = load(tuple(sorted({*US_CURVE.values(), *EA_CURVE.values(), *SPREADS, *PREMIUM})))
derived = build(stored, ["EA_SLOPE_10Y2Y", "EA_SLOPE_10Y3M", "ES_DE_SPREAD"])

st.title("Rates & Bonds")

# ----------------------------------------------------------------------------- yield curves

st.subheader("Yield curves")
for column, (region, curve) in zip(st.columns(2), CURVES.items(), strict=True):
    latest = stored[curve["10Y"]].index[-1]
    snapshots = [
        (f"Latest ({latest.day} {latest:%b %Y})", curve_on(stored, curve, latest)),
        ("1 month earlier", curve_on(stored, curve, latest - pd.DateOffset(months=1))),
        ("1 year earlier", curve_on(stored, curve, latest - pd.DateOffset(years=1))),
    ]
    with column:
        st.markdown(f"**{region}**")
        st.plotly_chart(curve_figure(snapshots), width="stretch")
        with st.expander("Data"):
            table = pd.DataFrame({label: c.set_index("tenor")["value"] for label, c in snapshots})
            st.dataframe(table.round(2), width="stretch")

# ----------------------------------------------------------------------------- spreads

st.subheader("Curve slope")
st.caption("Shaded: periods when 10Y-2Y was inverted (below zero).")
years = range_control("slope_range", default="20Y")

slopes = {
    "United States": {
        "10Y-2Y": stored["T10Y2Y"]["value"],
        "10Y-3M": stored["T10Y3M"]["value"],
    },
    "Euro area (AAA)": {
        "10Y-2Y": derived["EA_SLOPE_10Y2Y"]["value"],
        "10Y-3M": derived["EA_SLOPE_10Y3M"]["value"],
    },
}
for tab, lines in zip(st.tabs(list(slopes)), slopes.values(), strict=True):
    shown = {label: trailing(values, years) for label, values in lines.items()}
    with tab:
        figure = line_figure(shown, "Percentage points", shaded=runs_below(shown["10Y-2Y"]))
        st.plotly_chart(figure, width="stretch")

# ----------------------------------------------------------------------------- risk premium

st.subheader("Spain-Germany 10-year spread")
premium = derived["ES_DE_SPREAD"]["value"] * 100
last = premium.index[-1]
st.metric(
    f"Risk premium, {last:%B %Y} (monthly average)",
    f"{premium.iloc[-1]:.0f} bp",
    f"{premium.iloc[-1] - premium.iloc[-13]:+.0f} bp vs a year earlier",
    delta_color="inverse",
)
st.plotly_chart(line_figure({"ES-DE": premium}, "Basis points"), width="stretch")
st.caption("Source: ECB long-term interest rates (IRS), monthly averages of 10-year yields.")
