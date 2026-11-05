"""Overview: the handful of numbers and charts that summarise the macro picture at a glance."""

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.charts import color, curve_figure, line_figure
from app.data import load
from app.style import cards_on_canvas
from src.config import EA_CURVE, US_CURVE
from src.transform.curves import curve_on
from src.transform.series import spread, trailing

TARGET = 2.0  # ECB inflation target, percent
YEARS = 10  # every time series on the panel shows the same window, so they read side by side
# The page is a one-screen panel: the key figures and four chart cards must fit a 1080p
# browser window without scrolling
CHART_HEIGHT = 200
SPARK_MONTHS = 24  # history drawn under each key figure
# No Plotly toolbar: on a touch screen it stays visible and covers the legends
PLOT_CONFIG = {"displayModeBar": False}

cards_on_canvas()
st.html(
    "<style>"
    # On phones Streamlit stacks every column full width; keep the key figures two per row
    "@media (max-width: 640px) {.st-key-kpis [data-testid='stColumn']"
    "{min-width: calc(50% - 8px)}"
    # ...and let their labels wrap instead of ending in an ellipsis at half width
    ".st-key-kpis [data-testid='stMetricLabel'] *, .st-key-kpis [data-testid='stMetricDelta'] *"
    "{white-space: normal !important; text-overflow: clip}}"
    "</style>"
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


def card(title: str, subtitle: str) -> DeltaGenerator:
    """Bordered card with a bold title and a one-line grey subtitle (unit, window, source)."""
    box = st.container(border=True, key=f"card-{title}", gap="xxsmall")
    box.markdown(f"**{title}**  \n:gray[:small[{subtitle}]]")
    return box


def spark(values: pd.Series) -> list[float]:
    """Last SPARK_MONTHS of a series, one point per month, for the line under a key figure."""
    monthly = values.resample("MS").last().dropna()
    return monthly.iloc[-SPARK_MONTHS:].round(2).tolist()


# ----------------------------------------------------------------------------- key figures

tiles = st.container(key="kpis").columns(4)
with tiles[0]:
    change = round(cpi.iloc[-1] - cpi.iloc[-2], 1)
    st.metric(
        f"Spain inflation · {cpi.index[-1]:%b %Y}",
        f"{cpi.iloc[-1]:.1f}%",
        f"{change:+.1f} pp vs previous month" if change else "unchanged vs previous month",
        delta_color="inverse" if change else "off",
        delta_arrow="auto" if change else "off",
        border=True,
        chart_data=spark(cpi),
    )
with tiles[1]:
    st.metric(
        "ECB deposit rate",
        f"{deposit_rate.iloc[-1]:.2f}%",
        f"{deposit_rate.iloc[-1] - year_ago(deposit_rate):+.2f} pp in a year",
        delta_color="off",
        border=True,
        chart_data=spark(deposit_rate),
    )
with tiles[2]:
    st.metric(
        f"Spain 10-year bond · {spain_10y.index[-1]:%b %Y}",
        f"{spain_10y.iloc[-1]:.2f}%",
        f"{spain_10y.iloc[-1] - year_ago(spain_10y):+.2f} pp in a year",
        delta_color="off",
        border=True,
        chart_data=spark(spain_10y),
    )
with tiles[3]:
    st.metric(
        f"Risk premium vs Germany · {premium.index[-1]:%b %Y}",
        f"{premium.iloc[-1]:.0f} bp",
        f"{premium.iloc[-1] - year_ago(premium):+.0f} bp in a year",
        delta_color="inverse",
        border=True,
        chart_data=spark(premium),
    )

# ----------------------------------------------------------------------------- charts

left, right = st.columns(2)
with (
    left,
    card("Inflation in Spain", f"% y/y, last {YEARS} years · dotted line: ECB 2% target · INE"),
):
    lines = {"Headline": trailing(cpi, YEARS), "Core": trailing(core, YEARS)}
    figure = line_figure(lines, "", reference=TARGET, height=CHART_HEIGHT)
    st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
with right, card("Euro area yield curve", "% by maturity, AAA government bonds · ECB"):
    today = stored[EA_CURVE["10Y"]].index[-1]
    curves = [
        (f"{today.day} {today:%b %Y}", curve_on(stored, EA_CURVE, today), color(1)),
        (
            "1 year earlier",
            curve_on(stored, EA_CURVE, today - pd.DateOffset(years=1)),
            color(3),
        ),
    ]
    st.plotly_chart(
        curve_figure(curves, height=CHART_HEIGHT, y_title=""), width="stretch", config=PLOT_CONFIG
    )

left, right = st.columns(2)
with (
    left,
    card(
        "Spain-Germany risk premium",
        f"Basis points, 10-year yield gap, last {YEARS} years · ECB",
    ),
):
    figure = line_figure({"ES-DE": trailing(premium, YEARS)}, "", height=CHART_HEIGHT)
    st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
with (
    right,
    card(
        "Curve slope: 10-year minus 2-year",
        f"Percentage points, last {YEARS} years · below zero has preceded recessions",
    ),
):
    slopes = {
        "United States": trailing(
            spread(stored[US_CURVE["10Y"]], stored[US_CURVE["2Y"]])["value"], YEARS
        ),
        "Euro area": trailing(
            spread(stored[EA_CURVE["10Y"]], stored[EA_CURVE["2Y"]])["value"], YEARS
        ),
    }
    figure = line_figure(
        slopes,
        "",
        colors={"United States": color(1), "Euro area": color(2)},
        height=CHART_HEIGHT,
    )
    st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
