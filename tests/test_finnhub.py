"""News filtering tests. The items are invented: same structure as Finnhub's, no real text."""

import pandas as pd
import pytest

from src.ingest.finnhub import TOPICS, fetch_news, relevant_news, topic_of


def item(
    headline: str, summary: str = "", ts: int = 1793880000, source: str = "Example Wire"
) -> dict:
    return {
        "category": "top news",
        "datetime": ts,
        "headline": headline,
        "id": ts,
        "image": "",
        "related": "",
        "source": source,
        "summary": summary,
        "url": "https://example.com/story",
    }


def test_keeps_macro_news_and_drops_the_rest() -> None:
    items = [
        item("Central bank holds rates steady"),
        item("Retailer opens new stores"),
        item("Markets wrap", summary="Treasury yields rose after the jobs report"),
    ]
    assert list(relevant_news(items)["headline"]) == [
        "Central bank holds rates steady",
        "Markets wrap",
    ]


def test_keywords_match_whole_words_only() -> None:
    # "Fed" must not match "fedora", nor "bond" match "vagabond"
    assert relevant_news([item("Fedora maker buys vagabond brand")]).empty


def test_newest_first_without_duplicates() -> None:
    items = [
        item("Inflation cools", ts=1793800000),
        item("ECB signals pause", ts=1793900000),
        item("Inflation cools", ts=1793850000),  # the same story, republished
    ]
    news = relevant_news(items)
    assert list(news["headline"]) == ["ECB signals pause", "Inflation cools"]
    assert news.loc[0, "published"] == pd.Timestamp(1793900000, unit="s", tz="UTC")


def test_limit() -> None:
    items = [item(f"Bond market note {n}", ts=1793800000 + n) for n in range(40)]
    assert len(relevant_news(items, limit=25)) == 25


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.seen: dict = {}

    def get(self, url: str, params: dict, headers: dict, timeout: int) -> FakeResponse:
        self.seen = {"url": url, "params": params, "headers": headers}
        return FakeResponse(self.payload)


def test_key_goes_in_a_header_not_the_url() -> None:
    session = FakeSession([item("ECB meets")])
    fetch_news(session, "secret-key")
    assert session.seen["headers"] == {"X-Finnhub-Token": "secret-key"}
    assert "secret-key" not in session.seen["url"] + str(session.seen["params"])


def test_error_payload_is_an_error_not_news() -> None:
    with pytest.raises(RuntimeError, match="no news"):
        fetch_news(FakeSession({"error": "Invalid API key."}), "bad-key")


def test_source_suffix_and_echoed_summary_are_removed() -> None:
    news = relevant_news(
        [item("Oil slips on supply - Reuters", "Oil slips on supply  Reuters", source="Reuters")]
    )
    assert news.loc[0, "headline"] == "Oil slips on supply"
    assert news.loc[0, "summary"] == ""


def test_topic_comes_from_the_first_matching_group() -> None:
    assert topic_of("ECB worries about the economy") == "Central banks"
    assert topic_of("Euro zone economy shrinks") == "Europe"
    assert topic_of("Stocks rally as inflation cools") == "Inflation"
    assert topic_of("Gold hits a record") == "Markets"
    assert topic_of("Retailer opens new stores") is None


def test_headline_decides_the_topic_before_the_summary() -> None:
    assert topic_of("Treasury yields climb", "Stocks fell and the Fed spoke") == "Bonds"
    assert topic_of("Weekly wrap", "The Fed held rates") == "Central banks"


def test_every_keyword_belongs_to_exactly_one_topic() -> None:
    keywords = [k.lower() for group in TOPICS.values() for k in group]
    assert len(keywords) == len(set(keywords))


def test_news_carries_topic_and_image() -> None:
    news = relevant_news([item("Bond yields rise") | {"image": "https://example.com/a.jpg"}])
    assert news.loc[0, "topic"] == "Bonds"
    assert news.loc[0, "image"] == "https://example.com/a.jpg"
