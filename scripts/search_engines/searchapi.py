#!/usr/bin/env python3
"""B2H4 Content Hub - SearchAPI Connector.

SearchAPI.io: https://www.searchapi.io/
Free tier: 100 calls (teste)

Suporta múltiplos engines: google, bing, duckduckgo, etc.

Uso:
    connector = SearchAPIConnector()
    results = connector.search("AI agents 2026", max_results=5, engine="google")
"""

import os
import logging
from typing import List, Dict, Optional
from urllib.parse import urlencode

import requests

from .base import BaseSearchConnector

logger = logging.getLogger('search_engines.searchapi')

SEARCHAPI_BASE_URL = "https://www.searchapi.io/api/v1/search"


class SearchAPIConnector(BaseSearchConnector):
    """Conector de busca via SearchAPI.io.
    
    Env var necessária: SEARCHAPI_API_KEY
    
    Exemplos de uso:
        >>> s = SearchAPIConnector()
        >>> s.is_available()  # True se SEARCHAPI_API_KEY setada
        >>> results = s.search("AI agents 2026", max_results=5)
        >>> for r in results:
        ...     print(r['title'], r['url'])
    """
    
    name = "searchapi"
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SEARCHAPI_API_KEY", "")
    
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def search(
        self,
        query: str,
        max_results: int = 5,
        engine: str = "google",
        **kwargs
    ) -> List[Dict]:
        """Busca via SearchAPI.
        
        Args:
            query: Termo de busca
            max_results: Máximo de resultados (default: 5)
            engine: Motor de busca — 'google', 'bing', 'duckduckgo' (default: 'google')
            
        Returns:
            Lista de dicts padronizados
        """
        if not self.is_available():
            logger.debug("SearchAPI desativado (sem API key)")
            return []
        
        try:
            params = {
                "engine": engine,
                "q": query,
                "api_key": self._api_key,
                "num": min(max_results, 10),  # SearchAPI max = 10
            }
            
            url = f"{SEARCHAPI_BASE_URL}?{urlencode(params)}"
            logger.info(f"SearchAPI: '{query}' (engine={engine}, max={max_results})")
            
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            # SearchAPI retorna resultados em "organic_results"
            raw_results = data.get("organic_results", [])
            
            # Se não tem organic_results, tenta "results"
            if not raw_results:
                raw_results = data.get("results", [])
            
            logger.info(f"SearchAPI retornou {len(raw_results)} resultados")
            
            # Normaliza para formato padrão
            normalized = []
            for r in raw_results:
                normalized.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", r.get("url", "")),
                    "summary": r.get("snippet", r.get("description", "")),
                    "published": r.get("date", r.get("published_date", None)),
                    "source_name": f"searchapi:{engine}",
                    "raw": r,
                })
            
            return self._normalize_results(normalized)
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"SearchAPI HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            return []
        except requests.exceptions.Timeout:
            logger.error("SearchAPI timeout")
            return []
        except Exception as e:
            logger.error(f"SearchAPI erro inesperado: {type(e).__name__}: {e}")
            return []
