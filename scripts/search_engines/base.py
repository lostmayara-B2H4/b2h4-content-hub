#!/usr/bin/env python3
"""B2H4 Content Hub - Base Search Connector.

Classe abstrata para conectores de busca externos.
Cada conector retorna resultados no mesmo formato padronizado.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger('search_engines')


class BaseSearchConnector(ABC):
    """Classe base para conectores de busca.
    
    Cada conector deve implementar search() e is_available().
    Resultados retornam no formato padronizado:
    {
        "title": str,
        "url": str,
        "summary": str,
        "published": str (ISO date ou None),
        "source_name": str,
        "raw": dict (resposta original da API)
    }
    """
    
    name: str = "base"
    
    @abstractmethod
    def search(self, query: str, max_results: int = 5, **kwargs) -> List[Dict]:
        """Busca conteúdo por query.
        
        Args:
            query: Termo de busca
            max_results: Número máximo de resultados
            **kwargs: Parâmetros extras específicos de cada conector
            
        Returns:
            Lista de dicts com keys padronizadas
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o conector está configurado e disponível."""
        pass
    
    def _normalize_results(self, results: List[Dict]) -> List[Dict]:
        """Normaliza resultados para formato padrão do Content Hub."""
        normalized = []
        for r in results:
            normalized.append({
                "title": r.get("title", "").strip(),
                "url": r.get("url", r.get("link", "")).strip(),
                "summary": r.get("summary", r.get("snippet", r.get("content", ""))).strip(),
                "published": r.get("published", r.get("date", None)),
                "source_name": r.get("source_name", self.name),
                "raw": r
            })
        return normalized
