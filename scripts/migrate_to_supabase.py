#!/usr/bin/env python3
"""Migra dados do SQLite local para Supabase."""
import os, json, sqlite3

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

# Puxar do SQLite local
db_paths = [
    os.path.join(os.path.dirname(__file__), 'data', 'content_hub.db'),
    os.path.join(os.path.dirname(__file__), '..', 'data', 'content_hub.db'),
]
db_path = next((p for p in db_paths if os.path.exists(p)), None)
if not db_path:
    print("SQLite database not found at any path")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM content_items ORDER BY id')
items = [dict(row) for row in cur.fetchall()]
print(f'SQLite local: {len(items)} items')
conn.close()

if not items:
    print("Nenhum item para migrar")
    exit()

# Conectar Supabase
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL.startswith('postgresql://'):
    print("DATABASE_URL not set or invalid. Use Supabase pooler URL.")
    printer("Example: postgresql://postgres.PROJECT_REF:PASSWORD@aws-1-us-east-1.pooler.supabase.com:6543/postgres")
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
            if errors <= 3:
                print(f'  Erro [{errors}]: {e}')
    
    conn_pg.commit()
    print(f'Migrados: {imported} items para Supabase (erros: {errors})')
    
    cur_pg.execute('SELECT COUNT(*) as total FROM content_items')
    total = cur_pg.fetchone()['total']
    print(f'Total no Supabase agora: {total}')
    
    cur_pg.close()
    conn_pg.close()
except Exception as e:
    print(f'Erro: {e}')
