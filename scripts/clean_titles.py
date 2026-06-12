#!/usr/bin/env python3
"""Script para limpar títulos já existentes no banco de dados."""
import os, sys, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from database import clean_title, get_db

def clean_all_titles():
    """Limpa todos os títulos no banco de dados."""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Buscar todos os items
        if 'psycopg2' in str(type(conn)):
            cur.execute("SELECT id, title FROM content_items")
        else:
            cur.execute("SELECT id, title FROM content_items")
        
        rows = cur.fetchall()
        updated = 0
        
        for row in rows:
            item_id = row[0]
            old_title = row[1]
            
            if not old_title:
                continue
            
            new_title = clean_title(old_title)
            
            if new_title != old_title:
                if 'psycopg2' in str(type(conn)):
                    cur.execute("UPDATE content_items SET title = %s WHERE id = %s", (new_title, item_id))
                else:
                    cur.execute("UPDATE content_items SET title = ? WHERE id = ?", (new_title, item_id))
                updated += 1
                print(f'  [{item_id}] "{old_title[:50]}" → "{new_title[:50]}"')
        
        conn.commit()
        print(f'\n✅ {updated} títulos limpos')

if __name__ == '__main__':
    clean_all_titles()
