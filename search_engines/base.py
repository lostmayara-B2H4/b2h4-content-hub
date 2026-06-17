"""Search engine connectors base — ABC + result types."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published: str = ""
    score: float = 0.0
    raw: dict = field(default_factory=dict)


class BaseSearchConnector(ABC):
    """Abstract base for search engine connectors.

    Subclasses implement search() and is_available().
    If API key is missing, is_available() returns False
    and the connector is silently skipped by the registry.
    """

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this connector can be used (key configured, etc.)."""
        ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search and return list of SearchResult. Never raise — return [] on error."""
        ...

    def _safe_search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Wrapper that catches all exceptions and returns []."""
        try:
            if not self.is_available():
                return []
            return self.search(query, limit)
        except Exception:
            return []
