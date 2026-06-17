#!/usr/bin/env python3
"""B2H4 Content Hub - Search Connector Registry.

Registry central de conectores de busca.
Adiciona novos conectores aqui para que sejam usados automaticamente.
"""

import logging
from typing import List, Dict, Optional

from .base import BaseSearchConnector
from .tavily import TavilyConnector
from .searchapi import SearchAPIConnector

logger = logging.getLogger('search_engines.registry')

# ============================================================
# REGISTRY — Adicione novos conectores aqui
# ============================================================

_ALL_CONNECTORS: List[BaseSearchConnector] = [
    TavilyConnector(),
    SearchAPIConnector(),
]


def get_available_connectors() -> List[BaseSearchConnector]:
    """Retorna lista de conectores configurados (com API key)."""
    available = [c for c in _ALL_CONNECTORS if c.is_available()]
    logger.info(f"Conectores disponíveis: {[c.name for c in available]}")
    return available


def get_all_connectors() -> List[BaseSearchConnector]:
    """Retorna todos os conectores (incluindo desativados)."""
    return list(_ALL_CONNECTORS)


def search_all(
    query: str,
    max_results: int = 5,
    topic: str = "general",
    **kwargs
) -> List[Dict]:
    """Busca em todos os conectores disponíveis.
    
    Args:
        query: Termo de busca
        max_results: Máximo de resultados por conector
        topic: 'general' ou 'news' (para Tavily)
        
    Returns:
        Lista unificada de resultados (dedup por URL)
    """
    connectors = get_available_connectors()
    
    if not connectors:
        logger.warning("Nenhum conector de busca disponível (configure as API keys)")
        return []
    
    all_results = []
    seen_urls = set()
    
    for connector in connectors:
        try:
            # Tavily suporta topic; SearchAPI suporta engine
            if isinstance(connector, TavilyConnector):
                results = connector.search(
                    query, max_results=max_results, topic=topic, **kwargs
                )
            else:
                results = connector.search(
                    query, max_results=max_results, **kwargs
                )
            
            # Dedup por URL dentro deste conector
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
                elif not url:
                    all_results.append(r)
                    
        except Exception as e:
            logger.error(f"Erro no conector {connector.name}: {e}")
            continue
    
    logger.info(f"Total de resultados (dedup): {len(all_results)}")
    return all_results
