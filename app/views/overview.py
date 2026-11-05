"""Overview: the handful of numbers and charts that summarise the macro picture at a glance."""

import pandas as pd
import streamlit as st

from app.charts import color, curve_figure, line_figure
from app.data import load
from src.config import EA_CURVE, US_CURVE
from src.transform.curves import curve_on
from src.transform.series import spread, trailing

TARGET = 2.0  # ECB inflation target, percent

stored = load(
    tuple(
        sorted(
            {
                "ES_CPI",
                "ES_CPI_CORE",
                "EA_DFR",
                "ES_LTR_10Y",
                "DE_LTR_10Y",
                *EA_CURVE.values(),
                US_CURVE["10Y"],
                US_CURVE["2Y"],
            }
        )
    )
)
cpi = stored["ES_CPI"]["value"]
core = stored["ES_CPI_CORE"]["value"]
deposit_rate = stored["EA_DFR"]["value"]
spain_10y = stored["ES_LTR_10Y"]["value"]
premium = spread(stored["ES_LTR_10Y"], stored["DE_LTR_10Y"])["value"] * 100


def year_ago(values: pd.Series) -> float:
    """Value one year before the latest observation (last one on or before that date)."""
    return values.loc[: values.index[-1] - pd.DateOffset(years=1)].iloc[-1]


st.title("Macro at a glance")

# ----------------------------------------------------------------------------- key figures

tiles = st.columns(4)
with tiles[0]:
    change = round(cpi.iloc[-1] - cpi.iloc[-2], 1)
    st.metric(
        f"Spain inflation, {cpi.index[-1]:%b %Y}",
        f"{cpi.iloc[-1]:.1f}%",
        f"{change:+.1f} pp vs previous month" if change else "unchanged vs previous month",
        delta_color="inverse" if change else "off",
        delta_arrow="auto" if change else "off",
    )
with tiles[1]:
    st.metric(
        "ECB deposit rate",
        f"{deposit_rate.iloc[-1]:.2f}%",
        f"{deposit_rate.iloc[-1] - year_ago(deposit_rate):+.2f} pp in a year",
        delta_color="off",
    )
with tiles[2]:
    st.metric(
        f"Spain 10-year bond, {spain_10y.index[-1]:%b %Y}",
        f"{spain_10y.iloc[-1]:.2f}%",
        f"{spain_10y.iloc[-1] - year_ago(spain_10y):+.2f} pp in a year",
        delta_color="off",
    )
with tiles[3]:
    st.metric(
        f"Risk premium vs Germany, {premium.index[-1]:%b %Y}",
        f"{premium.iloc[-1]:.0f} bp",
        f"{premium.iloc[-1] - year_ago(premium):+.0f} bp in a year",
        delta_color="inverse",
    )

# ----------------------------------------------------------------------------- charts

left, right = st.columns(2)
with left:
    st.subheader("Inflation in Spain")
    lines = {"Headline": trailing(cpi, 10), "Core": trailing(core, 10)}
    st.plotly_chart(line_figure(lines, "Percent, y/y", reference=TARGET), width="stretch")
    st.caption("INE CPI. Dotted line: the ECB's 2% target.")
with right:
    st.subheader("Euro area yield curve")
    today = stored[EA_CURVE["10Y"]].index[-1]
    curves = [
        (f"{today.day} {today:%b %Y}", curve_on(stored, EA_CURVE, today), color(1)),
        (
            "1 year earlier",
            curve_on(stored, EA_CURVE, today - pd.DateOffset(years=1)),
            color(3),
        ),
    ]
    st.plotly_chart(curve_figure(curves), width="stretch")
    st.caption("AAA-rated euro area government bonds (ECB).")

left, right = st.columns(2)
with left:
    st.subheader("Spain-Germany risk premium")
    st.plotly_chart(line_figure({"ES-DE": premium}, "Basis points"), width="stretch")
    st.caption("Gap between Spanish and German 10-year yields, monthly averages (ECB).")
with right:
    st.subheader("Curve slope: 10-year minus 2-year")
    slopes = {
        "United States": trailing(
            spread(stored[US_CURVE["10Y"]], stored[US_CURVE["2Y"]])["value"], 20
        ),
        "Euro area": trailing(spread(stored[EA_CURVE["10Y"]], stored[EA_CURVE["2Y"]])["value"], 20),
    }
    figure = line_figure(
        slopes,
        "Percentage points",
        colors={"United States": color(1), "Euro area": color(2)},
    )
    st.plotly_chart(figure, width="stretch")
    st.caption("Below zero (inverted curve) has historically preceded recessions.")
