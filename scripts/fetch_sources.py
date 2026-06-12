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
    'engineering': ['engineering', 'developer', 'code', 'programming', 'api', 'framework', 'library', 'open source', 'github', 'deploy', 'infrastructure', 'cloud', 'devops', 'backend', 'frontend', 'fullstack', 'rust', 'python', 'javascript', 'typescript', 'go', 'docker', 'kubernetes'],
    'marketing': ['marketing', 'growth', 'seo', 'content', 'brand', 'social media', 'advertising', 'campaign', 'audience', 'engagement', 'conversion', 'funnel', 'acquisition', 'retention'],
    'finance': ['finance', 'investment', 'funding', 'venture', 'startup', 'valuation', 'ipo', 'revenue', 'profit', 'market', 'stock', 'crypto', 'fintech', 'banking'],
    'research': ['research', 'paper', 'arxiv', 'study', 'experiment', 'benchmark', 'model', 'neural', 'transformer', 'llm', 'gpt', 'diffusion', 'reinforcement', 'supervised', 'unsupervised'],
    'tools': ['tool', 'platform', 'app', 'software', 'saas', 'product', 'launch', 'release', 'update', 'feature', 'integration', 'automation', 'workflow', 'agent', 'copilot'],
    'regulation': ['regulation', 'policy', 'law', 'compliance', 'gdpr', 'privacy', 'safety', 'ethics', 'governance', 'ban', 'restrict', 'guideline', 'framework'],
}


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
        
        for entry in feed.entries[:20]:  # Limita a 20 por feed
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
        
        logger.info(f"  {name}: {len(items)} novos items")
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
        url = f"https://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=30"
        
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
        
        for entry in feed.entries[:10]:  # Limita a 10 por canal
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
        story_ids = resp.json()[:30]
        
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
        
        for entry in feed.entries[:15]:
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
    """Coleta repositórios trending do GitHub (via RSS)."""
    import feedparser
    items = []
    try:
        logger.info("Fetching GitHub Trending...")
        # GitHub trending não tem RSS oficial, usamos a página
        resp = requests.get('https://github.com/trending?since=daily', timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        
        from html.parser import HTMLParser
        
        class GitHubTrendingParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.repos = []
                self.in_repo = False
                self.current_repo = {}
                self.in_desc = False
            
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == 'article' and 'Box-row' in attrs_dict.get('class', ''):
                    self.in_repo = True
                    self.current_repo = {}
                elif self.in_repo and tag == 'h2':
                    self.in_repo = True
                elif self.in_repo and tag == 'a' and 'href' in attrs_dict:
                    href = attrs_dict['href']
                    if href.count('/') == 2 and not href.startswith('http'):
                        self.current_repo['url'] = f"https://github.com{href}"
                        self.current_repo['name'] = href.strip('/')
                elif self.in_repo and tag == 'p':
                    self.in_desc = True
            
            def handle_data(self, data):
                if self.in_repo and 'url' in self.current_repo and not self.current_repo.get('title'):
                    self.current_repo['title'] = data.strip()
                elif self.in_desc:
                    self.current_repo['desc'] = data.strip()
            
            def handle_endtag(self, tag):
                if tag == 'article' and self.in_repo:
                    if self.current_repo.get('url'):
                        self.repos.append(self.current_repo)
                    self.in_repo = False
                    self.current_repo = {}
                elif tag == 'p' and self.in_desc:
                    self.in_desc = False
        
        parser = GitHubTrendingParser()
        parser.feed(resp.text)
        
        for repo in parser.repos[:20]:
            if not repo.get('url') or is_url_seen(repo['url']):
                continue
            
            item = {
                'title': repo.get('title', ''),
                'url': repo['url'],
                'source_name': 'GitHub Trending',
                'source_type': 'github',
                'category': 'tools',
                'summary': repo.get('desc', ''),
                'raw_content': repo.get('desc', ''),
                'published_at': datetime.now(timezone.utc).isoformat(),
                'metadata': {'repo_name': repo.get('name', '')}
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
    
    # 1. RSS Feeds
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
