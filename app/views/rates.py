"""Rates & Bonds: yield curves, curve spreads with inversions, Spain-Germany risk premium."""

import pandas as pd
import streamlit as st

from app.charts import change_figure, color, curve_figure, line_figure, range_control
from app.data import load
from src.config import EA_CURVE, TENOR_YEARS, US_CURVE
from src.transform.curves import curve_change, curve_on, runs_below
from src.transform.series import spread, trailing

MARKETS = {"United States": US_CURVE, "Euro area (AAA)": EA_CURVE}
MARKET_SLOT = {"United States": 1, "Euro area (AAA)": 2}
PREMIUM = ("ES_LTR_10Y", "DE_LTR_10Y")

# Comparison dates for the curve, each with a fixed colour slot (slot 1 is the latest curve)
LOOKBACKS = {
    "1 month": pd.DateOffset(months=1),
    "3 months": pd.DateOffset(months=3),
    "1 year": pd.DateOffset(years=1),
    "3 years": pd.DateOffset(years=3),
}
SLOT = {"1 month": 2, "3 months": 3, "1 year": 4, "3 years": 5, "clicked": 6, "custom": 7}
SLOPE_CHART = "slope_chart"  # widget key: its click selection drives the curve section

stored = load(tuple(sorted({*US_CURVE.values(), *EA_CURVE.values(), *PREMIUM})))


def clicked_day() -> pd.Timestamp | None:
    """Day clicked on the slope chart in the previous run, if any."""
    event = st.session_state.get(SLOPE_CHART)
    points = event.selection.points if event else []
    return pd.Timestamp(points[0]["x"]).normalize() if points else None


st.title("Rates & Bonds")

# ----------------------------------------------------------------------------- yield curves

st.subheader("Yield curves")
controls = st.columns([3, 2, 2])
with controls[0]:
    lookbacks = st.pills(
        "Compare with", list(LOOKBACKS), selection_mode="multi", default=["1 month", "1 year"]
    )
with controls[1]:
    custom = st.date_input("…or a date of your choice", value=None, format="DD/MM/YYYY")
with controls[2]:
    view = st.segmented_control("Show", ["Levels", "Change (bp)"], default="Levels")

picked = clicked_day()
if picked is not None:
    st.caption(f"Also showing {picked.day} {picked:%b %Y}, clicked on the slope chart below.")

for column, (market, curve) in zip(st.columns(2), MARKETS.items(), strict=True):
    latest_day = stored[curve["10Y"]].index[-1]
    latest = curve_on(stored, curve, latest_day)
    earlier = [
        (f"{name} earlier", latest_day - offset, color(SLOT[name]))
        for name, offset in LOOKBACKS.items()
        if name in lookbacks
    ]
    for day, slot in ((picked, "clicked"), (custom, "custom")):
        if day is not None:
            day = pd.Timestamp(day)
            earlier.append((f"{day.day} {day:%b %Y}", day, color(SLOT[slot])))
    snapshots = [(label, curve_on(stored, curve, day), c) for label, day, c in earlier]
    snapshots = [s for s in snapshots if not s[1].empty]  # e.g. a date before the data starts

    latest_line = (f"Latest ({latest_day.day} {latest_day:%b %Y})", latest, color(1))
    with column:
        st.markdown(f"**{market}**")
        if view != "Change (bp)":
            st.plotly_chart(curve_figure([latest_line, *snapshots]), width="stretch")
        elif snapshots:
            changes = [
                (f"since {label.removesuffix(' earlier')}", curve_change(latest, c), clr)
                for label, c, clr in snapshots
            ]
            st.plotly_chart(change_figure(changes), width="stretch")
        else:
            st.info("Pick a comparison date to see how the curve moved.")
        with st.expander("Data"):
            levels = {
                label: c.set_index("tenor")["value"] for label, c, _ in [latest_line, *snapshots]
            }
            st.dataframe(pd.DataFrame(levels).round(2), width="stretch")

# ----------------------------------------------------------------------------- spreads

st.subheader("Curve slope")
tenors = list(TENOR_YEARS)
controls = st.columns([2, 2, 3, 3])
with controls[0]:
    long_tenor = st.selectbox("Long end", tenors, index=tenors.index("10Y"))
with controls[1]:
    short_tenor = st.selectbox("Short end", tenors, index=tenors.index("2Y"))
with controls[2]:
    markets = st.pills("Markets", list(MARKETS), selection_mode="multi", default=list(MARKETS))
with controls[3]:
    years = range_control("slope_range", default="20Y")

if TENOR_YEARS[long_tenor] <= TENOR_YEARS[short_tenor]:
    st.warning("Pick a long end with a longer maturity than the short end.")
elif not markets:
    st.info("Pick at least one market.")
else:
    label = f"{long_tenor}-{short_tenor}"
    lines = {
        market: trailing(
            spread(stored[MARKETS[market][long_tenor]], stored[MARKETS[market][short_tenor]])[
                "value"
            ],
            years,
        )
        for market in markets
    }
    # Shading is unambiguous only for one market at a time
    shaded = runs_below(next(iter(lines.values()))) if len(lines) == 1 else []
    figure = line_figure(
        lines,
        f"{label} (percentage points)",
        shaded=shaded,
        colors={market: color(MARKET_SLOT[market]) for market in lines},
        rangeslider=True,
        height=420,
    )
    st.plotly_chart(
        figure, width="stretch", on_select="rerun", selection_mode="points", key=SLOPE_CHART
    )
    hint = "Click any day to add its curve to the charts above; drag the bar below to zoom."
    st.caption(
        f"{hint} Shaded: periods when {label} was inverted (below zero)."
        if shaded
        else f"{hint} Pick a single market to shade its inversions."
    )

# ----------------------------------------------------------------------------- risk premium

st.subheader("Spain-Germany 10-year spread")
premium = spread(stored["ES_LTR_10Y"], stored["DE_LTR_10Y"])["value"] * 100
last = premium.index[-1]
controls = st.columns([2, 3, 5])
with controls[0]:
    st.metric(
        f"{last:%B %Y}",
        f"{premium.iloc[-1]:.0f} bp",
        f"{premium.iloc[-1] - premium.iloc[-13]:+.0f} bp vs a year earlier",
        delta_color="inverse",
    )
with controls[1]:
    premium_view = st.segmented_control("Show", ["Spread", "Yields"], default="Spread")
with controls[2]:
    premium_years = range_control("premium_range", default="All")

if premium_view == "Yields":
    yields = {
        "Spain 10Y": trailing(stored["ES_LTR_10Y"]["value"], premium_years),
        "Germany 10Y": trailing(stored["DE_LTR_10Y"]["value"], premium_years),
    }
    figure = line_figure(
        yields, "Yield (%)", colors={"Spain 10Y": color(2), "Germany 10Y": color(1)}
    )
else:
    figure = line_figure({"ES-DE": trailing(premium, premium_years)}, "Basis points")
st.plotly_chart(figure, width="stretch")
st.caption("Monthly averages of 10-year government bond yields. Source: ECB long-term rates (IRS).")
