#!/usr/bin/env python3
"""Migra dados do SQLite local para Supabase."""
import os, json, sqlite3, psycopg2
from psycopg2.extras import RealDictCursor

# Path correto do SQLite (apos refactor)
DB_PATH = '/Users/boris/b2h4-content-hub/data/content_hub.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM content_items ORDER BY id')
items = [dict(row) for row in cur.fetchall()]
print(f'SQLite local: {len(items)} items')
conn.close()

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("DATABASE_URL nao configurada")
    exit(1)

try:
    conn_pg = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur_pg = conn_pg.cursor()
    
    imported = 0
    errors = 0
    for item in items:
        try:
            cur_pg.execute("""
                INSERT INTO content_items (title, url, source_name, source_type, category, summary, raw_content, published_at, fetched_at, analyzed, importance, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (url) DO NOTHING
            """, (
                item['title'], item['url'], item['source_name'], item['source_type'],
                item.get('category'), item.get('summary'), item.get('raw_content'),
                item.get('published_at'), item.get('fetched_at'),
                bool(item.get('analyzed', 0)), item.get('importance', 0),
                json.dumps(item.get('metadata', {}))
            ))
            imported += 1
        except Exception as e:
            errors += 1
    
    conn_pg.commit()
    print(f'Migrados: {imported} items (erros: {errors})')
    
    cur_pg.execute('SELECT COUNT(*) as total FROM content_items')
    total_pg = cur_pg.fetchone()['total']
    print(f'Total no Supabase agora: {total_pg}')
    
    cur_pg.close()
    conn_pg.close()
except Exception as e:
    print(f'Erro: {e}')
