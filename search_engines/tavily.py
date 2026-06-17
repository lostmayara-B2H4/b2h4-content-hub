"""Tavily search connector."""
import os
from .base import BaseSearchConnector, SearchResult


class TavilyConnector(BaseSearchConnector):
    name = "tavily"

    def __init__(self):
        self._api_key = os.environ.get("TAVILY_API_KEY", "")
        self._base_url = "https://api.tavily.com"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        import requests

        resp = requests.post(
            f"{self._base_url}/search",
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
                "include_answer": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="tavily",
                    score=item.get("score", 0.0),
                    raw=item,
                )
            )
        return results
