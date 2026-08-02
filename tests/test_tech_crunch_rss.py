from scout_it import get_available_domains, search_entries, sort_entries


def test_sort_entries_orders_newest_first():
    entries = [
        {"title": "Older article", "published": "2023-01-01T00:00:00+00:00"},
        {"title": "Newer article", "published": "2024-01-01T00:00:00+00:00"},
    ]

    result = sort_entries(entries)

    assert [entry["title"] for entry in result] == ["Newer article", "Older article"]


def test_search_entries_includes_match_metadata():
    entries = [
        {
            "title": "OpenAI launches new agentic model",
            "summary": "The company unveiled a new agent framework for developers.",
            "author": "TechCrunch",
            "url": "https://techcrunch.com/openai-agents",
            "domain": "ai",
            "published": "2024-01-01T00:00:00+00:00",
        }
    ]

    result = search_entries(entries, "openai agents")

    assert result
    assert result[0]["score"] > 0
    assert result[0]["match_count"] > 0
    assert "openai" in result[0]["matched_terms"]
