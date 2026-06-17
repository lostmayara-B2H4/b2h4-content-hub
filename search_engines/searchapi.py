"""SearchAPI connector (https://www.searchapi.io)."""
import os
from .base import BaseSearchConnector, SearchResult


class SearchAPIConnector(BaseSearchConnector):
    name = "searchapi"

    def __init__(self):
        self._api_key = os.environ.get("SEARCHAPI_KEY", "")
        self._base_url = "https://www.searchapi.io/api/v1/search"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        import requests

        resp = requests.get(
            self._base_url,
            params={
                "engine": "google",
                "q": query,
                "limit": limit,
                "api_key": self._api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        # organic_results padrão do SearchAPI/Google
        for item in data.get("organic_results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="searchapi",
                    published=item.get("date", ""),
                    raw=item,
                )
            )
        return results
