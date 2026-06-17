"""Search engine registry — auto-discovers and aggregates results."""
from .base import BaseSearchConnector, SearchResult


class SearchRegistry:
    """Holds multiple connectors, deduplicates results by URL."""

    def __init__(self):
        self._connectors: list[BaseSearchConnector] = []

    def register(self, connector: BaseSearchConnector) -> None:
        self._connectors.append(connector)

    def available(self) -> list[BaseSearchConnector]:
        return [c for c in self._connectors if c.is_available()]

    def search_all(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search all available connectors, merge and deduplicate by URL."""
        seen_urls: set[str] = set()
        all_results: list[SearchResult] = []

        for conn in self.available():
            try:
                results = conn._safe_search(query, limit=limit)
                for r in results:
                    if r.url and r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception:
                continue  # never crash

        # Sort by score desc, then by source priority
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results


# Global singleton
_registry = SearchRegistry()


def get_registry() -> SearchRegistry:
    """Return the global search registry with all connectors pre-registered."""
    if not _registry._connectors:
        _auto_register()
    return _registry


def _auto_register() -> None:
    """Auto-discover all connector modules."""
    try:
        from .tavily import TavilyConnector
        _registry.register(TavilyConnector())
    except ImportError:
        pass

    try:
        from .searchapi import SearchAPIConnector
        _registry.register(SearchAPIConnector())
    except ImportError:
        pass
