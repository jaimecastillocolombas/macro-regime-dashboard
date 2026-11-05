"""Plotly figure builders shared by the pages: one look for every chart."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Categorical slots 1-3 of the reference palette (validated together, light and dark steps)
_SERIES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a"],
    "dark": ["#3987e5", "#d95926", "#199e70"],
}
_SHADE = {"light": "rgba(82, 81, 78, 0.12)", "dark": "rgba(195, 194, 183, 0.12)"}


RANGES: dict[str, int | None] = {"5Y": 5, "10Y": 10, "20Y": 20, "All": None}


def range_control(key: str, default: str) -> int | None:
    """Time-range selector shown above a chart; returns the years to show (None = all)."""
    chosen = st.segmented_control("Range", list(RANGES), default=default, key=key)
    return RANGES[chosen or "All"]  # clicking the selected option again clears it


def _mode() -> str:
    return "dark" if st.context.theme.type == "dark" else "light"


def series_colors() -> list[str]:
    return _SERIES[_mode()]


def _style(fig: go.Figure, y_title: str) -> go.Figure:
    fig.update_layout(
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(zeroline=False)
    return fig


def curve_figure(curves: list[tuple[str, pd.DataFrame]]) -> go.Figure:
    """One line per (label, curve), x = years to maturity on a log scale."""
    fig = go.Figure()
    for (label, curve), color in zip(curves, series_colors(), strict=False):
        fig.add_trace(
            go.Scatter(
                x=curve["years"],
                y=curve["value"],
                name=label,
                mode="lines+markers",
                line={"color": color, "width": 2},
                marker={"size": 8, "color": color},
                customdata=curve[["tenor"]],
                hovertemplate="%{customdata[0]}: %{y:.2f}%<extra>" + label + "</extra>",
            )
        )
    fig.update_layout(height=360)
    fig.update_xaxes(
        type="log",
        tickvals=curves[0][1]["years"],
        ticktext=curves[0][1]["tenor"],
        title="Maturity",
    )
    return _style(fig, "Yield (%)")


def line_figure(
    lines: dict[str, pd.Series],
    y_title: str,
    shaded: list[tuple[pd.Timestamp, pd.Timestamp]] = (),
    reference: float = 0.0,
    y_range: tuple[float, float] | None = None,
    height: int = 360,
) -> go.Figure:
    """Time series on one axis, a reference line (0 for spreads, 2 for inflation) and optional
    shaded periods behind them. Pass ``y_range`` to give small multiples the same scale."""
    fig = go.Figure()
    for start, end in shaded:
        fig.add_vrect(x0=start, x1=end, fillcolor=_SHADE[_mode()], line_width=0, layer="below")
    for (label, values), color in zip(lines.items(), series_colors(), strict=False):
        fig.add_trace(
            go.Scatter(
                x=values.index,
                y=values,
                name=label,
                mode="lines",
                line={"color": color, "width": 2},
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
