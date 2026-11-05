"""Inflation: headline vs core for Spain, the euro area and the US, and US 5y5y expectations."""

import pandas as pd
import streamlit as st

from app.charts import line_figure, range_control
from app.data import load
from src.transform.derived import build
from src.transform.series import trailing

TARGET = 2.0  # ECB and Fed inflation target, percent

# region -> (headline, core, where each one comes from)
REGIONS = {
    "Spain": ("ES_CPI", "ES_CPI_CORE", "INE CPI; core excludes unprocessed food and energy"),
    "Euro area": (
        "EA_HICP",
        "EA_HICP_CORE",
        "Eurostat HICP; core excludes energy, food, alcohol and tobacco",
    ),
    "United States": (
        "US_CPI_YOY",
        "US_CPI_CORE_YOY",
        "BLS CPI, not seasonally adjusted; core excludes food and energy",
    ),
}

stored = load(
    ("ES_CPI", "ES_CPI_CORE", "EA_HICP", "EA_HICP_CORE", "CPIAUCNS", "CPILFENS", "T5YIFR")
)
inflation = {**stored, **build(stored, ["US_CPI_YOY", "US_CPI_CORE_YOY"])}

st.title("Inflation")

# ----------------------------------------------------------------------------- latest readings

for column, (region, (headline, core, _)) in zip(st.columns(3), REGIONS.items(), strict=True):
    values = inflation[headline]["value"]
    core_values = inflation[core]["value"]
    change = round(values.iloc[-1] - values.iloc[-2], 1)  # the sources publish one decimal
    with column:
        st.metric(
            f"{region}, {values.index[-1]:%B %Y}",
            f"{values.iloc[-1]:.1f}%",
            f"{change:+.1f} pp vs previous month" if change else "unchanged vs previous month",
            delta_color="inverse" if change else "off",  # higher inflation shows red
            delta_arrow="auto" if change else "off",
        )
        st.caption(f"Core: {core_values.iloc[-1]:.1f}% ({core_values.index[-1]:%b %Y})")

# ----------------------------------------------------------------------------- headline vs core

st.subheader("Headline vs core, year-on-year")
st.caption(f"Dotted line: the {TARGET:.0f}% target. All three panels share the same scale.")
years = range_control("inflation_range", default="10Y")

panels = {
    region: {
        "Headline": trailing(inflation[headline]["value"], years),
        "Core": trailing(inflation[core]["value"], years),
    }
    for region, (headline, core, _) in REGIONS.items()
}
shown = pd.concat([s for lines in panels.values() for s in lines.values()])
padding = 0.5
y_range = (min(shown.min(), 0) - padding, shown.max() + padding)

for column, (region, lines) in zip(st.columns(3), panels.items(), strict=True):
    with column:
        st.markdown(f"**{region}**")
        figure = line_figure(lines, "Percent", reference=TARGET, y_range=y_range, height=320)
        st.plotly_chart(figure, width="stretch")
        st.caption(REGIONS[region][2])

with st.expander("Data"):
    table = pd.DataFrame(
        {
            f"{region} {label.lower()}": values
            for region, lines in panels.items()
            for label, values in lines.items()
        }
    ).sort_index(ascending=False)
    table.index = table.index.strftime("%Y-%m")
    st.dataframe(table.round(1), width="stretch")

# ----------------------------------------------------------------------------- expectations

st.subheader("Market inflation expectations: US 5y5y forward")
expectations = trailing(stored["T5YIFR"]["value"], years)
st.plotly_chart(line_figure({"5y5y": expectations}, "Percent", reference=TARGET), width="stretch")
st.caption(
    "Expected average inflation over the five years starting five years from now, implied by "
    "Treasury and TIPS yields (FRED T5YIFR). It tracks CPI, which runs a little above the PCE "
    "index the Fed targets. No free daily equivalent exists for the euro area."
)
