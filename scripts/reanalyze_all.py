#!/usr/bin/env python3
"""Reanalisa todos os itens do Content Hub em batches."""
import sys, time, json
sys.path.insert(0, 'scripts')
from database import get_db, _use_postgres, get_unanalyzed_items
from analyze_content import analyze_content_item

print("Iniciando reanálise de todos os itens...")

total_analyzed = 0
total_errors = 0
batch_num = 0

while True:
    items = get_unanalyzed_items(limit=10)
    if not items:
        print("\n✅ Todos os itens foram analisados!")
        break
    
    batch_num += 1
    print(f"\n--- Batch #{batch_num} ({len(items)} itens) ---")
    
    for item in items:
        try:
            analyze_content_item(item)
            total_analyzed += 1
            print(f"  ✅ #{item['id']} {item.get('title', '')[:50]}")
        except Exception as e:
            total_errors += 1
            print(f"  ❌ #{item['id']} ERRO: {e}")
    
    # Rate limit: aguardar entre batches
    if batch_num % 5 == 0:
        print(f"\n⏳ Pausa de 30s (rate limit)... Total: {total_analyzed} analisados")
        time.sleep(30)
    else:
        time.sleep(2)

print(f"\n{'='*50}")
print(f"RESUMO: {total_analyzed} analisados, {total_errors} erros")
