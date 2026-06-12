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
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "content_hub.db")


def _use_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


@contextmanager
def get_db() -> Generator[Any, None, None]:
    if _use_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = None
        for attempt in range(5):
            try:
                conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
                break
            except psycopg2.OperationalError:
                if attempt < 4:
                    import time
                    time.sleep(2)
                else:
                    raise
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
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
    """Limpa título removendo flairs, truncamentos e caracteres estranhos."""
    if not title:
        return title
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


def get_unanalyzed_items(limit: int = 50) -> List[Dict]:
    """Busca conteúdos não analisados."""
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("SELECT * FROM content_items WHERE analyzed = FALSE ORDER BY fetched_at DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT * FROM content_items WHERE analyzed = 0 ORDER BY fetched_at DESC LIMIT ?", (limit,))
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


def get_recent_items(hours: int = 24, category: str = None, limit: int = 50) -> List[Dict]:
    """Busca itens recentes, opcionalmente filtrados por categoria."""
    with get_db() as conn:
        cur = conn.cursor()
        if category:
            if _use_postgres():
                cur.execute("""
                    SELECT * FROM content_items
                    WHERE fetched_at > NOW() - INTERVAL '%s hours' AND category = %s
                    ORDER BY importance DESC, fetched_at DESC
                    LIMIT %s
                """, (hours, category, limit))
            else:
                cur.execute("""
                    SELECT * FROM content_items
                    WHERE fetched_at > datetime('now', ?) AND category = ?
                    ORDER BY importance DESC, fetched_at DESC
                    LIMIT ?
                """, (f'-{hours} hours', category, limit))
        else:
            if _use_postgres():
                cur.execute("""
                    SELECT * FROM content_items
                    WHERE fetched_at > NOW() - INTERVAL '%s hours'
                    ORDER BY importance DESC, fetched_at DESC
                    LIMIT %s
                """, (hours, limit))
            else:
                cur.execute("""
                    SELECT * FROM content_items
                    WHERE fetched_at > datetime('now', ?)
                    ORDER BY importance DESC, fetched_at DESC
                    LIMIT ?
                """, (f'-{hours} hours', limit))
        return [dict(row) for row in cur.fetchall()]


def is_url_seen(url: str) -> bool:
    """Verifica se URL já foi coletada."""
    with get_db() as conn:
        cur = conn.cursor()
        if _use_postgres():
            cur.execute("SELECT 1 FROM content_items WHERE url = %s", (url,))
        else:
            cur.execute("SELECT 1 FROM content_items WHERE url = ?", (url,))
        return cur.fetchone() is not None


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
