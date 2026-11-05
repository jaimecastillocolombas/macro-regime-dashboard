"""Shared page styling: white cards on a grey canvas, injected as CSS (no Streamlit calls
other than ``st.html``)."""

import streamlit as st

# Theme background is the card colour (charts are painted with it); pages that use cards sit
# them on a darker canvas, the theme's secondary background. Each pair is (light, dark).
CANVAS = ("#eceef2", "#0f1116")
CARD = ("#ffffff", "#181b21")


def cards_on_canvas() -> None:
    """Grey the page and fill every card: bordered containers keyed ``card-...`` and metrics.

    Streamlit draws those without a fill, so give them one; cards are found by the class
    Streamlit derives from their key. The colours are picked in the browser with CSS
    light-dark(), which follows the color-scheme Streamlit sets for the active theme:
    st.context.theme is only refreshed on a rerun, so switching theme from the menu would leave
    white cards on a dark page.
    """
    st.html(
        "<style>"
        "[data-testid='stAppViewContainer'], [data-testid='stHeader'] {"
        f"background: light-dark({CANVAS[0]}, {CANVAS[1]})}}"
        "[class*='st-key-card-'], [data-testid='stMetric'] {"
        f"background: light-dark({CARD[0]}, {CARD[1]});"
        "box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08)}"
        "</style>"
    )
