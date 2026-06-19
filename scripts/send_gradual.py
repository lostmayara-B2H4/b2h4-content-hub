#!/usr/bin/env python3
"""Envia itens analisados para newsletter em lotes pequenos para evitar rate limit."""
import requests, time, json, sys

HUB_URL = "https://b2h4-content-hub.onrender.com"
ADMIN_KEY = "1234"
BATCH_SIZE = 5
SLEEP_SECONDS = 15
MAX_BATCHES = 100

def get_total_analyzed():
    resp = requests.get(f"{HUB_URL}/health").json()
    return resp.get("analyzed_items", 0)

def send_batch(limit, offset):
    resp = requests.post(
        f"{HUB_URL}/api/send-analyzed",
        json={"limit": limit, "offset": offset},
        headers={"X-Admin-Key": ADMIN_KEY},
        timeout=120
    )
    return resp.json()

def main():
    total = get_total_analyzed()
    print(f"Total analisados no Hub: {total}")
    
    sent_total = 0
    found_total = 0
    offset = 0
    errors = []
    
    for batch_num in range(1, MAX_BATCHES + 1):
        print(f"\n--- Batch {batch_num} (offset={offset}, limit={BATCH_SIZE}) ---")
        try:
            result = send_batch(BATCH_SIZE, offset)
            print(f"  Resultado: {json.dumps(result, ensure_ascii=False)[:300]}")
            
            found = result.get("found", 0)
            sent = result.get("sent", 0)
            skipped = result.get("skipped_short", 0)
            found_total += found
            sent_total += sent
            
            if found == 0:
                print("  Nenhum item restante. Finalizando.")
                break
            
            if result.get("success"):
                print(f"  ✅ Enviados: {sent}/{found} (skipped_short: {skipped})")
                offset += found  # Avança offset pelo número de itens encontrados
            else:
                err = result.get("error", result.get("message", "erro desconhecido"))
                print(f"  ❌ Erro: {err}")
                errors.append(err)
                if "429" in str(err) or "rate" in str(err).lower():
                    print("  Rate limit detectado. Esperando 120s...")
                    time.sleep(120)
                    continue
            
            if batch_num < MAX_BATCHES:
                print(f"  Sleeping {SLEEP_SECONDS}s...")
                time.sleep(SLEEP_SECONDS)
                
        except requests.exceptions.Timeout:
            print("  ⏰ Timeout. Esperando 60s...")
            time.sleep(60)
        except Exception as e:
            print(f"  ❌ Exceção: {e}")
            time.sleep(30)
    
    print(f"\n{'='*50}")
    print(f"RESUMO: Enviados {sent_total} itens de {found_total} encontrados")
    if errors:
        print(f"Erros: {set(errors)}")

if __name__ == "__main__":
    main()
