"""Overview: the handful of numbers and charts that summarise the macro picture at a glance."""

import pandas as pd
import streamlit as st

from app.charts import color, curve_figure, line_figure
from app.data import load
from src.config import EA_CURVE, US_CURVE
from src.transform.curves import curve_on
from src.transform.series import spread, trailing

TARGET = 2.0  # ECB inflation target, percent
# The page is a one-screen panel: four charts in two rows must fit a laptop browser window
# (1440x900 screen) without scrolling, so the charts are shorter than elsewhere and the notes
# live in tooltips
CHART_HEIGHT = 220

# Streamlit pads the page with ~130 px above (under the 60 px top bar) and 160 px below; on a
# single-screen panel that is a fifth of the window, so trim it on this page only
st.html(
    "<style>[data-testid='stMainBlockContainer']{padding-top: 4.5rem; padding-bottom: 1rem}</style>"
)

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


def chart_title(title: str, note: str) -> None:
    """Bold one-line title with the source note behind a help icon, to save vertical space."""
    st.markdown(f"**{title}**", help=note)


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
    chart_title("Inflation in Spain", "INE CPI. Dotted line: the ECB's 2% target.")
    lines = {"Headline": trailing(cpi, 10), "Core": trailing(core, 10)}
    figure = line_figure(lines, "Percent, y/y", reference=TARGET, height=CHART_HEIGHT)
    st.plotly_chart(figure, width="stretch")
with right:
    chart_title("Euro area yield curve", "AAA-rated euro area government bonds (ECB).")
    today = stored[EA_CURVE["10Y"]].index[-1]
    curves = [
        (f"{today.day} {today:%b %Y}", curve_on(stored, EA_CURVE, today), color(1)),
        (
            "1 year earlier",
            curve_on(stored, EA_CURVE, today - pd.DateOffset(years=1)),
            color(3),
        ),
    ]
    st.plotly_chart(curve_figure(curves, height=CHART_HEIGHT), width="stretch")

left, right = st.columns(2)
with left:
    chart_title(
        "Spain-Germany risk premium",
        "Gap between Spanish and German 10-year yields, monthly averages (ECB).",
    )
    figure = line_figure({"ES-DE": premium}, "Basis points", height=CHART_HEIGHT)
    st.plotly_chart(figure, width="stretch")
with right:
    chart_title(
        "Curve slope: 10-year minus 2-year",
        "Below zero (inverted curve) has historically preceded recessions.",
    )
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
        height=CHART_HEIGHT,
    )
    st.plotly_chart(figure, width="stretch")
