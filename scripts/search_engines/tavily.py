#!/usr/bin/env python3
"""B2H4 Content Hub - Tavily Search Connector.

Tavily API: https://docs.tavily.com/
Free tier: 1.000 calls/mês

Uso:
    connector = TavilyConnector()
    results = connector.search("agentes IA autônomos", max_results=5)
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

import requests

from .base import BaseSearchConnector

logger = logging.getLogger('search_engines.tavily')

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilyConnector(BaseSearchConnector):
    """Conector de busca via Tavily API.
    
    Env var necessária: TAVILY_API_KEY
    
    Exemplos de uso:
        >>> t = TavilyConnector()
        >>> t.is_available()  # True se TAVILY_API_KEY setada
        >>> results = t.search("AI agents 2026", max_results=5)
        >>> for r in results:
        ...     print(r['title'], r['url'])
    """
    
    name = "tavily"
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
    
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def search(
        self,
        query: str,
        max_results: int = 5,
        topic: str = "general",
        search_depth: str = "basic",
        **kwargs
    ) -> List[Dict]:
        """Busca via Tavily API.
        
        Args:
            query: Termo de busca
            max_results: Máximo de resultados (default: 5)
            topic: 'general' ou 'news' (default: 'general')
            search_depth: 'basic' (rápido) ou 'advanced' (completo)
            
        Returns:
            Lista de dicts padronizados
        """
        if not self.is_available():
            logger.debug("Tavily desativado (sem API key)")
            return []
        
        try:
            payload = {
                "api_key": self._api_key,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "topic": topic,
            }
            
            logger.info(f"Tavily search: '{query}' (max={max_results}, topic={topic})")
            resp = requests.post(TAVILY_API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            raw_results = data.get("results", [])
            logger.info(f"Tavily retornou {len(raw_results)} resultados")
            
            # Normaliza para formato padrão
            normalized = []
            for r in raw_results:
                normalized.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "summary": r.get("content", ""),
                    "published": r.get("published_date", None),
                    "source_name": "tavily",
                    "raw": r,
                })
            
            return self._normalize_results(normalized)
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Tavily HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            return []
        except requests.exceptions.Timeout:
            logger.error("Tavily timeout")
            return []
        except Exception as e:
            logger.error(f"Tavily erro inesperado: {type(e).__name__}: {e}")
            return []
