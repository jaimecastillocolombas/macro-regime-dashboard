"""News: the latest macro-relevant headlines from Finnhub, fetched live.

The newest story leads with its picture; the rest follow in a three-card grid, grouped by day
(Madrid time) and tagged with their topic. One row of pills filters by topic.
"""

import pandas as pd
import streamlit as st

from app.data import news
from app.style import cards_on_canvas
from src.ingest.finnhub import TOPICS

LOCAL_TZ = "Europe/Madrid"
GRID_COLUMNS = 3
# Badge colour per topic. Red is left out: it reads as an alert, and none of these is one.
TOPIC_COLORS = {
    "Central banks": "blue",
    "Inflation": "orange",
    "Bonds": "violet",
    "Europe": "yellow",
    "Economy": "green",
    "Markets": "gray",
}
ALL = "All"

cards_on_canvas()
st.html(
    "<style>"
    # Same-height pictures however Finnhub's images are shaped, so the grid lines up
    ".st-key-card-news-lead img {height: 260px; object-fit: cover; width: 100%}"
    "[class*='st-key-card-news-item'] img {height: 150px; object-fit: cover; width: 100%}"
    # Grid summaries stop after three lines; the lead story shows its summary in full
    "[class*='st-key-card-news-item'] [data-testid='stCaptionContainer'] p {"
    "display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;"
    "overflow: hidden}"
    # Headlines read as headlines, not as blue underlined links, until hovered
    "[class*='st-key-card-news'] a {color: inherit; text-decoration: none}"
    "[class*='st-key-card-news'] a:hover {text-decoration: underline}"
    # Cards in a grid row share the height of the tallest one
    "[data-testid='stLayoutWrapper']:has(> [class*='st-key-card-news-item']) {flex: 1}"
    "[class*='st-key-card-news-item'] {height: 100%}"
    # On a phone the lead picture and headline would fill the screen
    "@media (max-width: 640px) {.st-key-card-news-lead img {height: 180px}"
    " .st-key-card-news-lead h3 {font-size: 1.25rem}}"
    "</style>"
)


def age_label(published: pd.Timestamp, now: pd.Timestamp) -> str:
    """How long ago a story was published: '12 min ago', '3 h ago' or '2 days ago'."""
    minutes = max(int((now - published).total_seconds() // 60), 0)
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 24 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} days ago" if minutes >= 48 * 60 else "1 day ago"


def day_label(day: pd.Timestamp, today: pd.Timestamp) -> str:
    """'Today', 'Yesterday' or the date, for the heading above each day's stories."""
    days = (today - day).days
    return {0: "Today", 1: "Yesterday"}.get(days, f"{day:%A} {day.day} {day:%B}")


def byline(row: pd.Series, now: pd.Timestamp) -> str:
    return f":gray[{row.source} · {age_label(row.published, now)}]"


def lead_story(row: pd.Series, now: pd.Timestamp) -> None:
    """The newest story: picture on the left, headline and full summary on the right."""
    with st.container(border=True, key="card-news-lead"):
        if row.image:
            picture, text = st.columns([2, 3], vertical_alignment="center")
            picture.image(row.image, width="stretch")
        else:
            text = st.container()
        with text:
            st.badge(row.topic, color=TOPIC_COLORS[row.topic])
            st.markdown(f"### [{row.headline}]({row.url})")
            if row.summary:
                st.markdown(row.summary)
            st.markdown(byline(row, now))


def story_card(row: pd.Series, now: pd.Timestamp, key: str) -> None:
    """A grid card: picture, topic, headline, a three-line summary and the byline."""
    with st.container(border=True, key=key):
        if row.image:
            st.image(row.image, width="stretch")
        st.badge(row.topic, color=TOPIC_COLORS[row.topic])
        st.markdown(f"**[{row.headline}]({row.url})**")
        if row.summary:
            st.caption(row.summary)
        st.markdown(byline(row, now))


st.title("News")
st.caption(
    "Macro headlines from Finnhub (Reuters, CNBC and others), tagged by topic. "
    "Refreshed every 15 minutes."
)

items = news()
if items is None:
    st.info("News needs a Finnhub API key: set FINNHUB_API_KEY in .env or the app's secrets.")
    st.stop()
if items.empty:
    st.info("No macro-relevant headlines in the latest Finnhub feed.")
    st.stop()

# Only offer the topics that have stories right now, in the fixed TOPICS order
present = [topic for topic in TOPICS if topic in set(items["topic"])]
chosen = st.pills("Topic", [ALL, *present], default=ALL, label_visibility="collapsed") or ALL
shown = items if chosen == ALL else items[items["topic"] == chosen]

now = pd.Timestamp.now(tz="UTC")
lead_story(shown.iloc[0], now)

rest = shown.iloc[1:].copy()
rest["day"] = rest["published"].dt.tz_convert(LOCAL_TZ).dt.normalize()
today = now.tz_convert(LOCAL_TZ).normalize()
for day, stories in rest.groupby("day", sort=False):
    st.markdown(f"#### {day_label(day, today)}")
    for start in range(0, len(stories), GRID_COLUMNS):
        row_of_cards = stories.iloc[start : start + GRID_COLUMNS]
        for column, (index, story) in zip(
            st.columns(GRID_COLUMNS), row_of_cards.iterrows(), strict=False
        ):
            with column:
                story_card(story, now, key=f"card-news-item-{index}")
