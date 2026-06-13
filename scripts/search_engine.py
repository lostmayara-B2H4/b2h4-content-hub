#!/usr/bin/env python3
"""B2H4 Content Hub - Free Search Engine.
Usa Google News RSS (gratuito, sem API key, sem limites).
Fallback: DuckDuckGo HTML scraping.
"""

import os
import re
import html as html_lib
import urllib.parse
import logging
import time
import requests
from typing import List, Dict
from datetime import datetime, timezone

logger = logging.getLogger('search_engine')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Queries de notícias de IA para buscar
AI_NEWS_QUERIES = [
    "AI artificial intelligence",
    "machine learning breakthrough",
    "OpenAI Anthropic Google DeepMind",
    "AI startup funding",
    "LLM large language model",
    "AI regulation policy",
    "AI tools new release",
    "deep learning research",
    "AI agent automation",
    "generative AI news",
]


def google_news_rss(query: str, num: int = 5, lang: str = 'en') -> List[Dict]:
    """Busca notícias via Google News RSS (100% gratuito, sem API key).
    
    Args:
        query: Termo de busca
        num: Número máximo de resultados
        lang: Idioma (en, pt, etc)
    
    Returns:
        Lista de dicts com 'title', 'url', 'source', 'published'
    """
    try:
        params = urllib.parse.quote(query)
        url = f'https://news.google.com/rss/search?q={params}&hl={lang}&gl=US&ceid=US:en'
        
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        
        xml = resp.text
        items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        
        results = []
        for item_xml in items[:num]:
            title = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
            link = re.search(r'<link>(.*?)</link>', item_xml, re.DOTALL)
            source = re.search(r'<source[^>]*>(.*?)</source>', item_xml, re.DOTALL)
            pub_date = re.search(r'<pubDate>(.*?)</pubDate>', item_xml, re.DOTALL)
            
            if title and link:
                clean_title = html_lib.unescape(title.group(1).strip())
                clean_link = link.group(1).strip()
                clean_source = html_lib.unescape(source.group(1).strip()) if source else 'Google News'
                clean_date = pub_date.group(1).strip() if pub_date else None
                
                results.append({
                    'title': clean_title,
                    'url': clean_link,
                    'source_name': clean_source,
                    'source_type': 'google_news',
                    'published_at': clean_date,
                })
        
        return results
    except Exception as e:
        logger.error(f"Google News RSS error: {e}")
        return []


def duckduckgo_search(query: str, num: int = 5) -> List[Dict]:
    """Busca no DuckDuckGo HTML (fallback, gratuito)."""
    try:
        url = f'https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        
        html_text = resp.text
        links = re.findall(
            r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>',
            html_text
        )
        
        results = []
        for raw_url, title in links[:num]:
            clean_title = html_lib.unescape(title).strip()
            if not clean_title:
                continue
            
            real_url = raw_url
            if raw_url.startswith('//duckduckgo.com/l/'):
                match = re.search(r'uddg=([^&]+)', raw_url)
                if match:
                    real_url = urllib.parse.unquote(match.group(1))
            
            results.append({
                'title': clean_title,
                'url': real_url,
                'source_name': 'DuckDuckGo',
                'source_type': 'search',
            })
        
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo error: {e}")
        return []


def fetch_ai_news(num_per_query: int = 5) -> List[Dict]:
    """Busca notícias de IA usando Google News RSS com múltiplas queries.
    
    Args:
        num_per_query: Resultados por query
    
    Returns:
        Lista deduplicada de notícias
    """
    all_results = []
    seen_urls = set()
    
    for query in AI_NEWS_QUERIES:
        results = google_news_rss(query, num=num_per_query)
        for r in results:
            url = r['url']
            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)
        time.sleep(0.5)  # Rate limit amigável
    
    logger.info(f"Search Engine: {len(all_results)} unique news from {len(AI_NEWS_QUERIES)} queries")
    return all_results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    print("=== B2H4 Search Engine Test ===\n")
    
    # Teste Google News RSS
    print("1. Google News RSS - AI news:")
    results = google_news_rss("AI artificial intelligence 2026", num=5)
    print(f"   Results: {len(results)}")
    for r in results:
        print(f"   - {r['title'][:70]}")
        print(f"     Source: {r['source_name']}")
    print()
    
    # Teste multi-query
    print("2. Multi-query AI news (3 per query):")
    news = fetch_ai_news(num_per_query=3)
    print(f"   Total unique: {len(news)}")
    for r in news[:10]:
        print(f"   - {r['title'][:70]} | {r['source_name']}")
