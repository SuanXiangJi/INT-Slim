import asyncio

import tavily

from app.tools.web_search_tool import WebSearchTool


def test_web_search_returns_sources_without_writing_sandbox(monkeypatch, tmp_path):
    class FakeClient:
        def __init__(self, _api_key):
            pass

        def search(self, **_kwargs):
            return {
                "results": [{
                    "title": "Example source",
                    "url": "https://example.com/source",
                    "content": "Verified content",
                }]
            }

    monkeypatch.setattr(tavily, "TavilyClient", FakeClient)

    result = asyncio.run(WebSearchTool().execute(
        {"query": "current information", "limit": 3},
        str(tmp_path),
    ))

    assert result["count"] == 1
    assert result["raw_data_saved"] is False
    assert result["raw_file"] is None
    assert list(tmp_path.iterdir()) == []
