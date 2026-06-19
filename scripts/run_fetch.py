#!/usr/bin/env python3
"""Script para rodar fetch_sources e salvar no banco."""
import os, sys, json

# Adicionar path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from fetch_sources import fetch_all_sources
from database import get_db, _use_postgres, init_db

def main():
    print("Iniciando fetch_sources...")
    stats = fetch_all_sources()
    print(f"Stats: {json.dumps(stats, indent=2)}")
    
    # Verificar total
    init_db()
    with get_db() as conn:
        if _use_postgres():
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM content_items")
            total = cur.fetchone()['cnt']
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM content_items").fetchone()
            total = row['cnt']
    print(f"Total content_items: {total}")

if __name__ == '__main__':
    main()
