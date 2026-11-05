"""Risk: fear gauges with their place in history, and euro area risk premia over Germany."""

import pandas as pd
import streamlit as st

from app.charts import color, line_figure
from app.data import load
from src.config import LONG_TERM_RATE_COUNTRIES
from src.transform.derived import build
from src.transform.series import percentile_rank, trailing

# gauge -> (series, label, unit format, explanation)
GAUGES = {
    "VIX": ("VIXCLS", "{:.1f}", "Expected 30-day volatility of the S&P 500, from option prices."),
    "Credit spread": (
        "BAA10Y",
        "{:.2f} pp",
        "Extra yield on Baa-rated US corporate bonds over 10-year Treasuries.",
    ),
    "Euro area stress (CISS)": (
        "EA_CISS",
        "{:.2f}",
        "ECB composite of stress in money, bond, equity and FX markets (0 to 1).",
    ),
}
PREMIA = [code for code in LONG_TERM_RATE_COUNTRIES if code != "DE"]
PREMIA_SINCE = pd.Timestamp("2007-01-01")  # before the 2008 and euro crises
PREMIA_CAP = 1300  # bp: Greece's 2012 peak would flatten every other line

stored = load(
    tuple(
        sorted(
            {series for series, *_ in GAUGES.values()}
            | {f"{code}_LTR_10Y" for code in LONG_TERM_RATE_COUNTRIES}
        )
    )
)
premia = build(stored, [f"{code}_DE_SPREAD" for code in PREMIA])


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


st.title("Risk")

# ----------------------------------------------------------------------------- fear gauges

st.subheader("Fear gauges")
st.caption(
    "Each reading is placed in its own history: the 90th percentile means fear has been "
    "lower than today on 90% of days. Dotted line: the historical median."
)
for column, (name, (series_id, fmt, about)) in zip(st.columns(3), GAUGES.items(), strict=True):
    values = stored[series_id]["value"]
    with column:
        st.metric(
            f"{name}, {values.index[-1].day} {values.index[-1]:%b %Y}",
            fmt.format(values.iloc[-1]),
            f"{ordinal(round(percentile_rank(values)))} percentile since {values.index[0]:%Y}",
            delta_color="off",
            delta_arrow="off",
        )
        figure = line_figure(
            {name: trailing(values, 20)}, "", reference=float(values.median()), height=260
        )
        st.plotly_chart(figure, width="stretch")
        st.caption(about)

# ----------------------------------------------------------------------------- risk premia

st.subheader("Risk premia over Germany, 10-year bonds")
latest = {code: premia[f"{code}_DE_SPREAD"]["value"] * 100 for code in PREMIA}
for column, (code, values) in zip(st.columns(len(PREMIA)), latest.items(), strict=True):
    with column:
        st.metric(
            f"{LONG_TERM_RATE_COUNTRIES[code]}, {values.index[-1]:%b %Y}",
            f"{values.iloc[-1]:.0f} bp",
            f"{values.iloc[-1] - values.iloc[-13]:+.0f} bp in a year",
            delta_color="inverse",
        )
lines = {
    LONG_TERM_RATE_COUNTRIES[code]: values.loc[PREMIA_SINCE:] for code, values in latest.items()
}
figure = line_figure(
    lines,
    "Basis points",
    colors={country: color(slot) for slot, country in enumerate(lines, start=1)},
    y_range=(0, PREMIA_CAP),
    height=420,
)
st.plotly_chart(figure, width="stretch")
greece = latest["GR"]
st.caption(
    f"Scale capped at {PREMIA_CAP:,} bp so the other countries stay readable: Greece peaked at "
    f"{greece.max():,.0f} bp in {greece.idxmax():%B %Y}. Monthly averages of 10-year government "
    "bond yields. Source: ECB long-term rates (IRS)."
)
