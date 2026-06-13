#!/usr/bin/env python3
"""B2H4 Content Hub - Database layer.
Reaproveita a conexão Supabase da newsletter.
"""

import os
import re as re_module
from contextlib import contextmanager
from typing import Generator, Any, Optional, Dict, List
from urllib.parse import urlparse, quote

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Global connection pool (lazy-initialized)
_pool = None
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "content_hub.db")


def _use_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


@contextmanager
def get_db() -> Generator[Any, None, None]:
    if _use_postgres():
        from psycopg2.extras import RealDictCursor
        global _pool
        if _pool is None:
            from psycopg2.pool import ThreadedConnectionPool
            _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL, cursor_factory=RealDictCursor)
        conn = _pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pool.putconn(conn)
    else:
        import sqlite3
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _init_sqlite(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _init_sqlite(conn):
    """Cria tabelas SQLite para dev local."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            category TEXT,
            summary TEXT,
            raw_content TEXT,
            published_at TIMESTAMPTZ,
            fetched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            analyzed BOOLEAN DEFAULT 0,
            importance INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS content_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER REFERENCES content_items(id) ON DELETE CASCADE,
            expert_role TEXT NOT NULL,
            analysis TEXT NOT NULL,
            key_insights TEXT DEFAULT '[]',
            relevance_score INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS content_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_id INTEGER,
            preferred_categories TEXT DEFAULT '[]',
            preferred_sources TEXT DEFAULT '[]',
            reading_history TEXT DEFAULT '[]',
            feedback_count INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS content_distribution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER REFERENCES content_items(id) ON DELETE CASCADE,
            subscriber_id INTEGER,
            channel TEXT NOT NULL,
            sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            opened BOOLEAN DEFAULT 0,
            clicked BOOLEAN DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_content_items_source ON content_items(source_type, fetched_at DESC);
        CREATE INDEX IF NOT EXISTS idx_content_items_analyzed ON content_items(analyzed) WHERE analyzed = 0;
    """)


def clean_title(title: str) -> str:
    """Limpa título removendo flairs, emojis, hashtags e truncamentos."""
    if not title:
        return title
    # Remove emojis (unicode ranges)
    title = re_module.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF]+', '', title).strip()
    # Remove hashtags: #word
    title = re_module.sub(r'#\w+', '', title).strip()
    # Remove flairs do Reddit: [P], [N], [D], [R], etc.
    title = re_module.sub(r'\s*\[([A-Z]{1,3})\]\s*$', '', title).strip()
    # Remove múltiplos espaços
    title = re_module.sub(r'\s+', ' ', title).strip()
    # Remove caracteres estranhos no final (/, -, |)
    title = re_module.sub(r'\s*[/\-|]\s*$', '', title).strip()
    return title if title else ''


def save_content_item(item: Dict) -> Optional[int]:
    """Salva um content_item. Retorna o ID ou None se duplicado."""
    # Limpa o título antes de salvar
    if item.get('title'):
        item['title'] = clean_title(item['title'])
    # Limpa remojis do summary também
    if item.get('summary'):
        import re as _re
        item['summary'] = _re.sub(r'[^\x00-\x7F\xC0-\xFF\u0100-\u024F\u1E00-\u1EFF]+', '', item['summary']).strip()
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("""
                INSERT INTO content_items (title, url, source_name, source_type, category, summary, raw_content, published_at, metadata)
                VALUES (%(title)s, %(url)s, %(source_name)s, %(source_type)s, %(category)s, %(summary)s, %(raw_content)s, %(published_at)s, %(metadata)s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
            """, {**item, 'metadata': str(item.get('metadata', {}))})
            row = cur.fetchone()
            return row['id'] if row else None
        else:
            try:
                cur.execute("""
                    INSERT INTO content_items (title, url, source_name, source_type, category, summary, raw_content, published_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['title'], item['url'], item['source_name'], item['source_type'],
                      item.get('category'), item.get('summary'), item.get('raw_content'),
                      item.get('published_at'), str(item.get('metadata', {}))))
                return cur.lastrowid
            except Exception:
                return None


def send_to_newsletter(content_id: int) -> bool:
    """Envia um content_item para a tabela news_items da newsletter."""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Busca o item no Content Hub
        if _use_postgres():
            cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE id = %s", (content_id,))
        else:
            cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE id = ?", (content_id,))
        
        item = cur.fetchone()
        if not item:
            return False
        
        # Verifica se já foi enviado
        if _use_postgres():
            cur.execute("SELECT 1 FROM news_items WHERE source_url = %s", (item['url'],))
        else:
            cur.execute("SELECT 1 FROM news_items WHERE source_url = ?", (item['url'],))
        
        if cur.fetchone():
            return False  # Já existe
        
        # Insere na news_items da newsletter
        title = item.get('title', '')[:300]
        summary = item.get('summary', '')[:1000] if item.get('summary') else ''
        source_url = item.get('url', '')
        source_name = item.get('source_name', 'Content Hub')
        category = item.get('category', 'general')
        
        if _use_postgres():
            cur.execute("""
                INSERT INTO news_items (title, summary, source_url, source_name, category, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
            """, (title, summary, source_url, source_name, category))
        else:
            cur.execute("""
                INSERT INTO news_items (title, summary, source_url, source_name, category, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))
            """, (title, summary, source_url, source_name, category))
        
        conn.commit()
        return True
def get_unanalyzed_items(limit: int = 10) -> List[Dict]:
    """Busca conteúdos não analisados."""
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("SELECT id, title, url, source_name, source_type, category, summary, raw_content, published_at, fetched_at, analyzed, importance, metadata FROM content_items WHERE analyzed = FALSE ORDER BY fetched_at DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT id, title, url, source_name, source_type, category, summary, raw_content, published_at, fetched_at, analyzed, importance, metadata FROM content_items WHERE analyzed = 0 ORDER BY fetched_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]


def mark_analyzed(content_id: int):
    """Marca conteúdo como analisado."""
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("UPDATE content_items SET analyzed = TRUE WHERE id = %s", (content_id,))
        else:
            cur.execute("UPDATE content_items SET analyzed = 1 WHERE id = ?", (content_id,))


def save_analysis(content_id: int, expert_role: str, analysis: str, insights: list, relevance: int):
    """Salva análise de um expert role."""
    with get_db() as conn:
        cur = conn.cursor()
        import json
        if _use_postgres():
            cur.execute("""
                INSERT INTO content_analysis (content_id, expert_role, analysis, key_insights, relevance_score)
                VALUES (%s, %s, %s, %s, %s)
            """, (content_id, expert_role, analysis, json.dumps(insights), relevance))
        else:
            cur.execute("""
                INSERT INTO content_analysis (content_id, expert_role, analysis, key_insights, relevance_score)
                VALUES (?, ?, ?, ?, ?)
            """, (content_id, expert_role, analysis, json.dumps(insights), relevance))


def get_recent_items(hours: int = 24, category: str = None, search: str = None, sort: str = 'date', limit: int = 50, offset: int = 0) -> tuple:
    """Busca itens recentes com filtros SQL. Retorna (items, total)."""
    cols = "id, title, url, source_name, source_type, category, summary, raw_content, published_at, fetched_at, analyzed, importance, metadata"
    with get_db() as conn:
        cur = conn.cursor()
        # Build WHERE clause
        conditions = []
        params = []
        if _use_postgres():
            conditions.append("fetched_at > NOW() - INTERVAL '%s hours'")
            params.append(hours)
        else:
            conditions.append("fetched_at > datetime('now', ?)")
            params.append(f'-{hours} hours')
        if category:
            conditions.append("category = %s" if _use_postgres() else "category = ?")
            params.append(category)
        if search:
            conditions.append("title ILIKE %s" if _use_postgres() else "title LIKE ?")
            params.append(f'%{search}%')
        where_clause = " AND ".join(conditions)
        # Count total
        count_sql = f"SELECT COUNT(*) as cnt FROM content_items WHERE {where_clause}"
        cur.execute(count_sql, params)
        total = cur.fetchone()['cnt']
        # ORDER BY
        if sort == 'relevance':
            order_clause = "analyzed ASC, importance DESC, fetched_at DESC"
        else:
            order_clause = "importance DESC, fetched_at DESC"
        # Main query with LIMIT/OFFIX
        if _use_postgres():
            query_sql = f"SELECT {cols} FROM content_items WHERE {where_clause} ORDER BY {order_clause} LIMIT %s OFFSET %s"
        else:
            query_sql = f"SELECT {cols} FROM content_items WHERE {where_clause} ORDER BY {order_clause} LIMIT ? OFFSET ?"
        cur.execute(query_sql, params + [limit, offset])
        items = [dict(row) for row in cur.fetchall()]
        return items, total


def is_url_seen(url: str) -> bool:
    """Verifica se URL já foi coletada."""
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("SELECT 1 FROM content_items WHERE url = %s", (url,))
        else:
            cur.execute("SELECT 1 FROM content_items WHERE url = ?", (url,))
        return cur.fetchone() is not None


def get_existing_urls(urls: list) -> set:
    """Busca todas as URLs de uma vez. Retorna set de URLs já existentes."""
    if not urls:
        return set()
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("SELECT url FROM content_items WHERE url = ANY(%s)", (urls,))
        else:
            placeholders = ','.join(['?' for _ in urls])
            cur.execute(f"SELECT url FROM content_items WHERE url IN ({placeholders})", urls)
        return {row['url'] for row in cur.fetchall()}


def save_content_items_batch(items: list) -> int:
    """Salva múltiplos items em uma única transação. Retorna count de inseridos."""
    if not items:
        return 0
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            from psycopg2.extras import execute_values
            values = [
                (i['title'], i['url'], i['source_name'], i['source_type'],
                 i.get('category'), i.get('summary'), i.get('raw_content'),
                 i.get('published_at'), str(i.get('metadata', {})))
                for i in items
            ]
            execute_values(cur, """
                INSERT INTO content_items (title, url, source_name, source_type, category, summary, raw_content, published_at, metadata)
                VALUES %s
                ON CONFLICT (url) DO NOTHING
            """, values)
        else:
            import sqlite3
            count = 0
            for i in items:
                try:
                    cur.execute("""
                        INSERT INTO content_items (title, url, source_name, source_type, category, summary, raw_content, published_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (i['title'], i['url'], i['source_name'], i['source_type'],
                          i.get('category'), i.get('summary'), i.get('raw_content'),
                          i.get('published_at'), str(i.get('metadata', {}))))
                    count += 1
                except Exception:
                    pass
            return count
        return len(items)


def get_stats() -> Dict:
    """Retorna estatísticas gerais."""
    with get_db() as conn:
        cur = conn.cursor()
        stats = {}
        if _use_postgres():
            cur.execute("SELECT COUNT(*) as total FROM content_items")
            stats['total_items'] = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM content_items WHERE analyzed = TRUE")
            stats['analyzed_items'] = cur.fetchone()['total']
            cur.execute("SELECT source_type, COUNT(*) as count FROM content_items GROUP BY source_type")
            stats['by_source'] = {row['source_type']: row['count'] for row in cur.fetchall()}
            cur.execute("SELECT category, COUNT(*) as count FROM content_items WHERE category IS NOT NULL GROUP BY category")
            stats['by_category'] = {row['category']: row['count'] for row in cur.fetchall()}
        else:
            cur.execute("SELECT COUNT(*) as total FROM content_items")
            stats['total_items'] = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM content_items WHERE analyzed = 1")
            stats['analyzed_items'] = cur.fetchone()['total']
            cur.execute("SELECT source_type, COUNT(*) as count FROM content_items GROUP BY source_type")
            stats['by_source'] = {row['source_type']: row['count'] for row in cur.fetchall()}
            cur.execute("SELECT category, COUNT(*) as count FROM content_items WHERE category IS NOT NULL GROUP BY category")
            stats['by_category'] = {row['category']: row['count'] for row in cur.fetchall()}
        return stats
