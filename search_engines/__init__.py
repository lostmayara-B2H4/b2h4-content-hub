"""Search engines package — plug-and-play connectors."""
from .base import BaseSearchConnector, SearchResult
from .registry import get_registry

__all__ = ["BaseSearchConnector", "SearchResult", "get_registry"]


def get_available_connectors() -> list[BaseSearchConnector]:
    """Return list of available (key-configured) connectors."""
    return get_registry().available()


def search_all(query: str, limit: int = 10, topic: str = "general") -> list[dict]:
    """Search all available connectors, return unified list of dicts."""
    results = get_registry().search_all(query, limit=limit)
    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "source_name": r.source,
            "published": r.published,
            "score": r.score,
        }
        for r in results
    ]
