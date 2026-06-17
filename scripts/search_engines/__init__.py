#!/usr/bin/env python3
"""B2H4 Content Hub - Search Engines Module.

Conectores de busca externos (Tavily, SearchAPI).
Plug and play: adicione a API key e o conector ativa automaticamente.

Uso:
    from search_engines import search_all, get_available_connectors
    
    # Busca em todos os conectores disponíveis
    results = search_all("AI agents", max_results=5, topic="news")
    
    # Lista conectores ativos
    connectors = get_available_connectors()
"""

from .base import BaseSearchConnector
from .tavily import TavilyConnector
from .searchapi import SearchAPIConnector
from .registry import (
    get_available_connectors,
    get_all_connectors,
    search_all,
)

__all__ = [
    "BaseSearchConnector",
    "TavilyConnector",
    "SearchAPIConnector",
    "get_available_connectors",
    "get_all_connectors",
    "search_all",
]
