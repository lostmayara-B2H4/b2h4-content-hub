# Teste de startup simplificado - ignora import errors
cd ~/b2h4-content-hub && python3 -c "
import sys
try:
    from app import app
    print('APP OK')
except Exception as e:
    print(f'ERRO: {e}')
    # Tenta importar uma por uma
    print('Testando imports individuais...')
    for mod in ['flask', 'feedparser', 'requests', 'psycopg2', 'gunicorn']:
        try:
            __import__(mod)
            print(f'  {mod}: OK')
        except ImportError:
            print(f'  {mod}: NOT FOUND')
" 2>&1