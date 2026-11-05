"""Plotly figure builders shared by the pages: one look for every chart."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Categorical palette, in its validated order (light and dark steps of the same eight hues).
# Pages pick a fixed slot per entity, so toggling one series never repaints the others.
_SERIES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
}
_SHADE = {"light": "rgba(82, 81, 78, 0.12)", "dark": "rgba(195, 194, 183, 0.12)"}


RANGES: dict[str, int | None] = {"5Y": 5, "10Y": 10, "20Y": 20, "All": None}


def range_control(key: str, default: str) -> int | None:
    """Time-range selector shown above a chart; returns the years to show (None = all)."""
    chosen = st.segmented_control("Range", list(RANGES), default=default, key=key)
    return RANGES[chosen or "All"]  # clicking the selected option again clears it


def _mode() -> str:
    return "dark" if st.context.theme.type == "dark" else "light"


def color(slot: int) -> str:
    """Colour of categorical slot ``slot`` (1-based) for the current theme."""
    return _SERIES[_mode()][slot - 1]


def series_colors() -> list[str]:
    return _SERIES[_mode()]


def _style(fig: go.Figure, y_title: str) -> go.Figure:
    fig.update_layout(
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        font={"family": "Inter, sans-serif", "size": 11},  # same typeface as the app theme
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font_size": 12},
        yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(zeroline=False)
    return fig


def _maturity_axis(fig: go.Figure, curve: pd.DataFrame) -> None:
    """Log-scaled maturity axis labelled with the tenors (3M ... 30Y)."""
    fig.update_xaxes(type="log", tickvals=curve["years"], ticktext=curve["tenor"], title="Maturity")


def curve_figure(curves: list[tuple[str, pd.DataFrame, str]], height: int = 380) -> go.Figure:
    """One line per (label, curve, colour), x = years to maturity on a log scale."""
    fig = go.Figure()
    for label, curve, line_color in curves:
        fig.add_trace(
            go.Scatter(
                x=curve["years"],
                y=curve["value"],
                name=label,
                mode="lines+markers",
                line={"color": line_color, "width": 2},
                marker={"size": 8, "color": line_color},
                customdata=curve[["tenor"]],
                hovertemplate="%{customdata[0]}: %{y:.2f}%<extra>" + label + "</extra>",
            )
        )
    fig.update_layout(height=height)
    _maturity_axis(fig, curves[0][1])
    return _style(fig, "Yield (%)")


def line_figure(
    lines: dict[str, pd.Series],
    y_title: str,
    shaded: list[tuple[pd.Timestamp, pd.Timestamp]] = (),
    reference: float = 0.0,
    y_range: tuple[float, float] | None = None,
    height: int = 360,
    colors: dict[str, str] | None = None,
) -> go.Figure:
    """Time series on one axis, a reference line (0 for spreads, 2 for inflation) and optional
    shaded periods behind them. Pass ``y_range`` to give small multiples the same scale and
    ``colors`` to pin a colour to each series."""
    fig = go.Figure()
    for start, end in shaded:
        fig.add_vrect(x0=start, x1=end, fillcolor=_SHADE[_mode()], line_width=0, layer="below")
    default_colors = dict(zip(lines, series_colors(), strict=False))
    for label, values in lines.items():
        fig.add_trace(
            go.Scatter(
                x=values.index,
                y=values,
                name=label,
                mode="lines",
                line={"color": (colors or default_colors)[label], "width": 2},
                hovertemplate="%{y:.2f}",
            )
        )
    fig.add_hline(
        y=reference, line_width=1, line_dash="dot" if reference else "solid", line_color="gray"
    )
    # A single series needs no legend: the section title names it
    fig.update_layout(hovermode="x unified", showlegend=len(lines) > 1, height=height)
    if y_range is not None:
        fig.update_yaxes(range=list(y_range))
    return _style(fig, y_title)
