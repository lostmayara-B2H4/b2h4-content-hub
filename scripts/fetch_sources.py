#!/usr/bin/env python3
"""B2H4 Content Hub - Content Source Fetcher.
Coleta conteúdo de fontes gratuitas: RSS, arXiv, YouTube RSS, Hacker News, Reddit, GitHub.
Tudo 100% gratuito, sem API keys.
"""

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import urlparse

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('fetch_sources')

# Adiciona path do database
sys.path.insert(0, os.path.dirname(__file__))
from database import save_content_item, is_url_seen, get_stats

# ============================================================
# FONTES DE CONTEÚDO (100% gratuitas)
# ============================================================

# RSS Feeds de tecnologia/AI
RSS_FEEDS = {
    # Blogs de tecnologia
    'techcrunch': 'https://techcrunch.com/feed/',
    'the_verge': 'https://www.theverge.com/rss/index.xml',
    'wired': 'https://www.wired.com/feed/rss',
    'ars_technica': 'https://feeds.arstechnica.com/arstechnica/index',
    'hacker_news': 'https://hnrss.org/frontpage',
    'mit_tech_review': 'https://www.technologyreview.com/feed/',
    
    # AI/ML específicos
    'openai_blog': 'https://openai.com/blog/rss.xml',
    'deepmind_blog': 'https://deepmind.google/discover/blog/rss.xml',
    'google_ai': 'https://blog.google/technology/ai/rss/',
    'huggingface': 'https://huggingface.co/blog/feed.xml',
    'langchain': 'https://blog.langchain.dev/rss/',
    'anthropic_blog': 'https://www.anthropic.com/news/rss.xml',
    'mistral': 'https://mistral.ai/news/rss.xml',
    
    # Brasil
    'tecmundo': 'https://www.tecmundo.com.br/rss',
    'canaltech': 'https://feeds.feedburner.com/canaltechbr',
    'startse': 'https://www.startse.com/feed/',
    
    # Startups/Growth
    'product_hunt': 'https://www.producthunt.com/feed',
    'ycombinator': 'https://www.ycombinator.com/rss',
    'first_round': 'https://review.firstround.com/feed',
}

# Canais YouTube (via RSS - sem API key)
YOUTUBE_CHANNELS = {
    'lex_fridman': 'UCJIfeSCssNspxS4tG3VPyag',
    'two_minute_papers': 'UCbfYPyITQ-7l4upoX8nvctg',
    'yannic_kilcher': 'UCZHmQk67mSJgfCCTn7xBfew',
    'sentdex': 'UCfzlCWGWYyIQ0aLC5w48gBQ',
    '3blue1brown': 'UCYO_jab_esuFRV4b17AJtAw',
    'ai_explained': 'UCNJ1Ymd5O9FAyiNfV-GtyGg',
    'fireship': 'UCsBjURrPoezykLs9EqgamOA',
    'theo_t3dotgg': 'UCbRP3c757lWg9M-U7TyEk9A',
}

# Subreddits (via RSS - sem API key)
SUBREDDITS = [
    'MachineLearning',
    'artificial',
    'LocalLLaMA',
    'ChatGPT',
    'OpenAI',
    'startups',
    'Entrepreneur',
    'technology',
    'programming',
    'webdev',
    'datascience',
    'Futurology',
]

# Categorias de classificação
CATEGORY_KEYWORDS = {
    'engineering': ['engineering', 'developer', 'code', 'programming', 'api', 'framework', 'library', 'open source', 'github', 'deploy', 'infrastructure', 'cloud', 'devops', 'backend', 'frontend', 'fullstack', 'rust', 'python', 'javascript', 'typescript', 'go', 'docker', 'kubernetes', 'system', 'architecture', 'database', 'server', 'microservice', 'ci/cd', 'testing', 'debug', 'refactor'],
    'marketing': ['marketing', 'growth', 'seo', 'content', 'brand', 'social media', 'advertising', 'campaign', 'audience', 'engagement', 'conversion', 'funnel', 'acquisition', 'retention', 'viral', 'launch', 'product hunt', 'newsletter', 'email', 'copywriting', 'pitch'],
    'finance': ['finance', 'investment', 'funding', 'venture', 'startup', 'valuation', 'ipo', 'revenue', 'profit', 'market', 'stock', 'crypto', 'fintech', 'banking', 'raised', 'series', 'seed', 'valuation', 'unicorn', 'acquisition', 'merger'],
    'research': ['research', 'paper', 'arxiv', 'study', 'experiment', 'benchmark', 'model', 'neural', 'transformer', 'llm', 'gpt', 'diffusion', 'reinforcement', 'supervised', 'unsupervised', 'deep learning', 'machine learning', 'ai', 'artificial intelligence', 'nlp', 'computer vision', 'robotics', 'algorithm', 'dataset', 'training', 'inference', 'fine-tuning', 'rlhf', 'attention', 'embedding', 'token', 'multimodal', 'agent', 'reasoning'],
    'tools': ['tool', 'platform', 'app', 'software', 'saas', 'product', 'release', 'update', 'feature', 'integration', 'automation', 'workflow', 'copilot', 'ide', 'editor', 'cli', 'sdk', 'plugin', 'extension', 'dashboard', 'analytics', 'monitoring'],
    'regulation': ['regulation', 'policy', 'law', 'compliance', 'gdpr', 'privacy', 'safety', 'ethics', 'governance', 'ban', 'restrict', 'guideline', 'framework', 'act', 'bill', 'congress', 'senate', 'court', 'lawsuit', 'antitrust'],
}


def clean_title(title: str, source_type: str = '') -> str:
    """Limpa título removendo flairs, truncamentos e caracteres estranhos."""
    import re
    
    # Remove flairs do Reddit: [P], [N], [D], [R], etc.
    title = re.sub(r'\s*\[([A-Z]{1,3})\]\s*$', '', title).strip()
    
    # Remove múltiplos espaços
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Remove caracteres estranhos no final (/, -, |)
    title = re.sub(r'\s*[/\-|]\s*$', '', title).strip()
    
    # Se ficou vazio, retorna original
    if not title:
        return title
    
    return title


def classify_category(title: str, summary: str = '') -> str:
    """Classifica conteúdo por categoria baseado em keywords."""
    text = f"{title} {summary}".lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return 'general'


def fetch_rss_feed(name: str, url: str) -> List[Dict]:
    """Coleta items de um feed RSS."""
    import feedparser
    items = []
    try:
        logger.info(f"Fetching RSS: {name} ({url})")
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning(f"Feed vazio ou erro: {name}")
            return items
        
        for entry in feed.entries[:5]:  # Top 5 mais relevantes por feed RSS
            url_entry = entry.get('link', '')
            if not url_entry or is_url_seen(url_entry):
                continue
            
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            published_at = None
            if published:
                published_at = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            
            summary = entry.get('summary', '') or entry.get('description', '')
            # Limpa HTML do summary
            import re
            summary = re.sub(r'<[^>]+>', '', summary)[:500]
            
            item = {
                'title': entry.get('title', ''),
                'url': url_entry,
                'source_name': name,
                'source_type': 'rss',
                'category': classify_category(entry.get('title', ''), summary),
                'summary': summary,
                'raw_content': entry.get('content', [{}])[0].get('value', '') if entry.get('content') else summary,
                'published_at': published_at,
                'metadata': {'feed_url': url}
            }
            items.append(item)
        
        logger.info(f"  {name}: {len(items)} novos items (top 5)")
    except Exception as e:
        logger.error(f"Erro no feed {name}: {e}")
    
    return items


def fetch_arxiv() -> List[Dict]:
    """Coleta papers do arXiv API (gratuito, sem key)."""
    items = []
    try:
        logger.info("Fetching arXiv API...")
        # Busca papers de IA/ML dos últimos dias
        query = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV"
        url = f"https://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=5"
        
        import feedparser
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            url_entry = entry.get('link', '')
            if not url_entry or is_url_seen(url_entry):
                continue
            
            published = entry.get('published_parsed')
            published_at = None
            if published:
                published_at = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            
            summary = entry.get('summary', '')
            import re
            summary = re.sub(r'<[^>]+>', '', summary)[:500]
            
            item = {
                'title': entry.get('title', '').replace('\n', ' ').strip(),
                'url': url_entry,
                'source_name': 'arXiv',
                'source_type': 'arxiv',
                'category': 'research',
                'summary': summary,
                'raw_content': entry.get('summary', ''),
                'published_at': published_at,
                'metadata': {'authors': [a.get('name', '') for a in entry.get('authors', [])]}
            }
            items.append(item)
        
        logger.info(f"  arXiv: {len(items)} novos papers")
    except Exception as e:
        logger.error(f"Erro no arXiv: {e}")
    
    return items


def fetch_youtube_rss(channel_name: str, channel_id: str) -> List[Dict]:
    """Coleta vídeos do YouTube via RSS (sem API key)."""
    import feedparser
    items = []
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:5]:  # Top 5 mais relevantes por canal
            url_entry = entry.get('link', '')
            if not url_entry or is_url_seen(url_entry):
                continue
            
            published = entry.get('published_parsed')
            published_at = None
            if published:
                published_at = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            
            item = {
                'title': entry.get('title', ''),
                'url': url_entry,
                'source_name': f"YouTube/{channel_name}",
                'source_type': 'youtube',
                'category': classify_category(entry.get('title', '')),
                'summary': entry.get('summary', '')[:500],
                'raw_content': entry.get('summary', ''),
                'published_at': published_at,
                'metadata': {'channel_id': channel_id, 'channel_name': channel_name}
            }
            items.append(item)
        
        if items:
            logger.info(f"  YouTube/{channel_name}: {len(items)} novos vídeos")
    except Exception as e:
        logger.error(f"Erro no YouTube {channel_name}: {e}")
    
    return items


def fetch_hackernews() -> List[Dict]:
    """Coleta do Hacker News API (gratuito, sem key)."""
    items = []
    try:
        logger.info("Fetching Hacker News...")
        # Busca top stories
        resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        story_ids = resp.json()[:5]  # Top 5 mais relevantes do HN
        
        for story_id in story_ids:
            try:
                story = requests.get(
                    f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
                    timeout=5
                ).json()
                
                if not story or story.get('type') != 'story':
                    continue
                
                url = story.get('url', '')
                if not url:
                    url = f"https://news.ycombinator.com/item?id={story_id}"
                
                if is_url_seen(url):
                    continue
                
                published_at = None
                if story.get('time'):
                    published_at = datetime.fromtimestamp(story['time'], tz=timezone.utc).isoformat()
                
                item = {
                    'title': story.get('title', ''),
                    'url': url,
                    'source_name': 'Hacker News',
                    'source_type': 'hackernews',
                    'category': classify_category(story.get('title', '')),
                    'summary': f"Score: {story.get('score', 0)} | Comments: {story.get('descendants', 0)}",
                    'raw_content': story.get('text', ''),
                    'published_at': published_at,
                    'metadata': {'score': story.get('score', 0), 'comments': story.get('descendants', 0), 'hn_id': story_id}
                }
                items.append(item)
                time.sleep(0.1)  # Rate limit
            except Exception:
                continue
        
        logger.info(f"  Hacker News: {len(items)} novos items")
    except Exception as e:
        logger.error(f"Erro no HN: {e}")
    
    return items


def fetch_reddit_rss(subreddit: str) -> List[Dict]:
    """Coleta do Reddit via RSS (sem API key)."""
    import feedparser
    items = []
    try:
        url = f"https://old.reddit.com/r/{subreddit}/.rss"
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:5]:  # Top 5 mais relevantes por subreddit
            url_entry = entry.get('link', '')
            if not url_entry or is_url_seen(url_entry):
                continue
            
            published = entry.get('published_parsed')
            published_at = None
            if published:
                published_at = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            
            summary = entry.get('summary', '')
            import re
            summary = re.sub(r'<[^>]+>', '', summary)[:500]
            
            item = {
                'title': entry.get('title', ''),
                'url': url_entry,
                'source_name': f"Reddit/r/{subreddit}",
                'source_type': 'reddit',
                'category': classify_category(entry.get('title', ''), summary),
                'summary': summary,
                'raw_content': summary,
                'published_at': published_at,
                'metadata': {'subreddit': subreddit}
            }
            items.append(item)
        
        if items:
            logger.info(f"  Reddit/r/{subreddit}: {len(items)} novos items")
    except Exception as e:
        logger.error(f"Erro no Reddit {subreddit}: {e}")
    
    return items


def fetch_github_trending() -> List[Dict]:
    """Coleta repositórios trending do GitHub via API (gratuita, sem key)."""
    items = []
    try:
        logger.info("Fetching GitHub Trending...")
        # Usa a API pública do GitHub (rate limit: 60 req/h sem auth)
        resp = requests.get(
            'https://api.github.com/search/repositories?q=created:>2026-06-01&sort=stars&order=desc&per_page=15',
            timeout=10,
            headers={'Accept': 'application/vnd.github.v3+json'}
        )
        
        if resp.status_code != 200:
            logger.warning(f"GitHub API returned {resp.status_code}")
            return items
        
        data = resp.json()
        for repo in data.get('items', [])[:5]:  # Top 5 mais relevantes do GitHub
            repo_name = repo.get('full_name', '') or repo.get('name', '')
            if not repo_name:
                continue
            
            url = repo.get('html_url', '')
            if not url or is_url_seen(url):
                continue
            
            desc = repo.get('description', '') or ''
            lang = repo.get('language', '') or ''
            stars = repo.get('stargazers_count', 0)
            
            # Título: repo_name: description (truncado em 80 chars)
            title = repo_name
            if desc:
                short_desc = desc[:80] + ('...' if len(desc) > 80 else '')
                title += f": {short_desc}"
            
            summary = desc[:500] if desc else f"⭐ {stars:,} stars"
            
            item = {
                'title': title,
                'url': url,
                'source_name': f'GitHub Trending',
                'source_type': 'github',
                'category': 'tools',
                'summary': summary,
                'raw_content': desc,
                'published_at': datetime.now(timezone.utc).isoformat(),
                'metadata': {'repo': repo_name, 'stars': stars, 'lang': lang}
            }
            items.append(item)
        
        logger.info(f"  GitHub Trending: {len(items)} novos repos")
    except Exception as e:
        logger.error(f"Erro no GitHub: {e}")
    
    return items


def fetch_all_sources() -> Dict:
    """Coleta todas as fontes e salva no banco."""
    all_items = []
    stats = {'total_new': 0, 'by_source': {}}
    
    # 0. Google News RSS (motor de busca gratuito)
    logger.info("=" * 50)
    logger.info("FASE 0: Google News RSS Search Engine")
    logger.info("=" * 50)
    try:
        from search_engine import fetch_ai_news
        search_results = fetch_ai_news(num_per_query=5)
        for item in search_results:
            if not is_url_seen(item['url']):
                result = save_content_item({
                    'title': item['title'],
                    'url': item['url'],
                    'source_name': item.get('source_name', 'Google News'),
                    'source_type': 'google_news',
                    'category': classify_category(item['title']),
                    'summary': '',
                    'raw_content': '',
                    'published_at': item.get('published_at'),
                    'metadata': {'query': 'search_engine'}
                })
                if result:
                    stats['total_new'] += 1
                    stats['by_source']['google_news'] = stats['by_source'].get('google_news', 0) + 1
        logger.info(f"  Google News RSS: {stats['by_source'].get('google_news', 0)} new items")
    except Exception as e:
        logger.error(f"Error in Google News RSS: {e}")
    
    time.sleep(1)
    logger.info("=" * 50)
    logger.info("FASE 1: RSS Feeds")
    logger.info("=" * 50)
    for name, url in RSS_FEEDS.items():
        items = fetch_rss_feed(name, url)
        for item in items:
            result = save_content_item(item)
            if result:
                stats['total_new'] += 1
                stats['by_source'][name] = stats['by_source'].get(name, 0) + 1
        time.sleep(0.5)  # Rate limit entre feeds
    
    # 2. arXiv
    logger.info("=" * 50)
    logger.info("FASE 2: arXiv")
    logger.info("=" * 50)
    items = fetch_arxiv()
    for item in items:
        result = save_content_item(item)
        if result:
            stats['total_new'] += 1
            stats['by_source']['arxiv'] = stats['by_source'].get('arxiv', 0) + 1
    time.sleep(1)
    
    # 3. Hacker News
    logger.info("=" * 50)
    logger.info("FASE 3: Hacker News")
    logger.info("=" * 50)
    items = fetch_hackernews()
    for item in items:
        result = save_content_item(item)
        if result:
            stats['total_new'] += 1
            stats['by_source']['hackernews'] = stats['by_source'].get('hackernews', 0) + 1
    time.sleep(1)
    
    # 4. YouTube RSS (primeiros 5 canais)
    logger.info("=" * 50)
    logger.info("FASE 4: YouTube RSS")
    logger.info("=" * 50)
    for name, channel_id in list(YOUTUBE_CHANNELS.items())[:5]:
        items = fetch_youtube_rss(name, channel_id)
        for item in items:
            result = save_content_item(item)
            if result:
                stats['total_new'] += 1
                stats['by_source'][f'youtube_{name}'] = stats['by_source'].get(f'youtube_{name}', 0) + 1
        time.sleep(0.5)
    
    # 5. Reddit (primeiros 5 subreddits)
    logger.info("=" * 50)
    logger.info("FASE 5: Reddit RSS")
    logger.info("=" * 50)
    for subreddit in SUBREDDITS[:5]:
        items = fetch_reddit_rss(subreddit)
        for item in items:
            result = save_content_item(item)
            if result:
                stats['total_new'] += 1
                stats['by_source'][f'reddit_{subreddit}'] = stats['by_source'].get(f'reddit_{subreddit}', 0) + 1
        time.sleep(0.5)
    
    # 6. GitHub Trending
    logger.info("=" * 50)
    logger.info("FASE 6: GitHub Trending")
    logger.info("=" * 50)
    items = fetch_github_trending()
    for item in items:
        result = save_content_item(item)
        if result:
            stats['total_new'] += 1
            stats['by_source']['github'] = stats['by_source'].get('github', 0) + 1
    
    logger.info("=" * 50)
    logger.info(f"COLETA COMPLETA: {stats['total_new']} novos items")
    logger.info(f"Por fonte: {json.dumps(stats['by_source'], indent=2)}")
    
    return stats


if __name__ == '__main__':
    stats = fetch_all_sources()
    print(json.dumps(stats, indent=2))
