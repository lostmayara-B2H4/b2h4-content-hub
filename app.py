#!/usr/bin/env python3
"""B2H4 Content Hub - Flask Dashboard."""

import os
import sys
import json
import math
import secrets
import threading
import logging
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify
from flask_caching import Cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, get_stats, get_recent_items, clean_title

# App start time for uptime tracking
APP_START_TIME = datetime.now(timezone.utc)

# Simple in-memory rate limit cache for analyze-batch
_rate_limit_lock = threading.Lock()
_last_analyze_call = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ── Cache Configuration (P1-2) ───────────────────────────────────────
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app)

@app.template_filter('fmt_date')
def fmt_date(dt):
    if dt is None:
        return ''
    if isinstance(dt, str):
        return dt[:16]
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y %H:%M')
    return str(dt)[:16]

# ── Admin Key (P1-4) ─────────────────────────────────────────────────
ADMIN_KEY = os.environ.get('ADMIN_KEY')
if not ADMIN_KEY:
    ADMIN_KEY = secrets.token_hex(16)
    logging.getLogger('app').warning(f"ADMIN_KEY não configurada. Gerada automaticamente: {ADMIN_KEY}")

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.args.get('key') or request.headers.get('X-Admin-Key')
        if key != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    """Dashboard principal com paginação, busca e ordenação."""
    stats = get_stats()
    
    # Parâmetros
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    category = request.args.get('category', None)
    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'date')
    
    # Busca com filtros SQL (P1-1)
    items, total = get_recent_items(
        hours=24*30,
        category=category,
        search=query if query else None,
        sort=sort,
        limit=per_page,
        offset=(page - 1) * per_page
    )
    
    total_pages = max(1, math.ceil(total / per_page)) if total > 0 else 1
    page = max(1, min(page, total_pages))
    
    return render_template('index.html', 
                         stats=stats, 
                         items=items,
                         current_page=page,
                         total_pages=total_pages,
                         total_items=total,
                         per_page=per_page)


@app.route('/api/stats')
@cache.cached(timeout=60)
def api_stats():
    return jsonify(get_stats())


@app.route('/api/items')
@cache.cached(timeout=300)
def api_items():
    hours = request.args.get('hours', 24, type=int)
    category = request.args.get('category', None)
    query = request.args.get('q', '').strip()
    items, total = get_recent_items(hours=hours, category=category, search=query if query else None, limit=1000, offset=0)
    return jsonify({'items': items, 'count': total})


@app.route('/api/trigger-fetch', methods=['POST'])
@require_admin
def trigger_fetch():
    from fetch_sources import fetch_all_sources
    return jsonify(fetch_all_sources())


@app.route('/api/trigger-analyze', methods=['POST'])
@require_admin
def trigger_analyze():
    from analyze_content import analyze_batch
    limit = request.args.get('limit', 10, type=int)
    return jsonify(analyze_batch(limit=limit))


@app.route('/api/trigger-distribute', methods=['POST'])
@require_admin
def trigger_distribute():
    from distribute import send_daily_digest
    return jsonify(send_daily_digest())


@app.route('/api/debug')
def debug():
    keys = ['OPENROUTER_API_KEY', 'DATABASE_URL', 'RESEND_API_KEY', 'TELEGRAM_BOT_TOKEN']
    result = {}
    for k in keys:
        v = os.environ.get(k, '')
        result[k] = f"✓ ({v[:8]}...{v[-4:]})" if v else "✗ NÃO configurada"
    return jsonify(result)
@app.route('/api/send-to-newsletter/<int:content_id>', methods=['POST'])
@require_admin
def send_to_newsletter(content_id):
    """Envia um item do Content Hub para a newsletter."""
    from database import send_to_newsletter as _send
    result = _send(content_id)
    if result:
        return jsonify({'success': True, 'message': 'Enviado para newsletter!'})
    else:
        return jsonify({'success': False, 'message': 'Item não encontrado ou já enviado'}), 400


@app.route('/api/analyze-and-send', methods=['POST'])
@require_admin
def analyze_and_send():
    """Analisa itens não analisados e envia para newsletter.
    
    Body opcional: {"content_ids": [1, 2, 3]} — se não fornecido, analisa todos não-analisados
    """
    import traceback as _tb
    from database import get_all_content_ids, _use_postgres, get_db
    from analyze_content import analyze_content_item
    from database import send_to_newsletter
    
    try:
        data = request.get_json(silent=True) or {}
        content_ids = data.get('content_ids', None)
        
        if not content_ids:
            # Busca todos os não-analizados
            with get_db() as conn:
                cur = conn.cursor()
                if _use_postgres():
                    cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE analyzed = FALSE ORDER BY fetched_at DESC LIMIT 50")
                else:
                    cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE analyzed = 0 ORDER BY fetched_at DESC LIMIT 50")
                items = [dict(r) for r in cur.fetchall()]
                content_ids = [i['id'] for i in items]
        
        if not content_ids:
            return jsonify({'success': True, 'analyzed': 0, 'sent': 0, 'message': 'Nenhum item para analisar'})
        
        analyzed = 0
        sent = 0
        errors = []
        
        for cid in content_ids[:50]:  # Max 50 por chamada
            try:
                # Busca item
                with get_db() as conn:
                    cur = conn.cursor()
                    if _use_postgres():
                        cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE id = %s", (cid,))
                    else:
                        cur.execute("SELECT id, title, url, source_name, category, summary FROM content_items WHERE id = ?", (cid,))
                    item = cur.fetchone()
                
                if not item:
                    continue
                item = dict(item)
                
                # Analisa se não foi analisado
                if not item.get('analyzed'):
                    analyze_content_item(item)
                    analyzed += 1
                
                # Envia para newsletter
                if send_to_newsletter(cid):
                    sent += 1
                    
            except Exception as e:
                errors.append({'id': cid, 'error': str(e), 'trace': _tb.format_exc()[-500:]})
        
        return jsonify({
            'success': True,
            'analyzed': analyzed,
            'sent': sent,
            'errors': errors
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': _tb.format_exc()[-1000:]
        }), 500

@app.route('/api/test-send/<int:content_id>', methods=['POST'])
@require_admin
def test_send(content_id):
    """Testa send_to_newsletter para um item específico."""
    import traceback as _tb
    from database import send_to_newsletter, get_db, _use_postgres
    
    result = {'content_id': content_id, 'postgres': _use_postgres()}
    
    try:
        # Verificar se o item existe
        with get_db() as conn:
            cur = conn.cursor()
            if _use_postgres():
                cur.execute("SELECT id, title, url, source_name, category, summary, analyzed FROM content_items WHERE id = %s", (content_id,))
            else:
                cur.execute("SELECT id, title, url, source_name, category, summary, analyzed FROM content_items WHERE id = ?", (content_id,))
            item = cur.fetchone()
            if item:
                result['item'] = dict(item)
            else:
                result['error'] = 'Item not found'
                return jsonify(result)
        
        # Verificar se news_items existe
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM news_items")
                cnt = cur.fetchone()
                result['news_items_count'] = cnt[0] if cnt else str(cnt)
            except Exception as e:
                result['news_items_error'] = str(e)
        
        # Tentar enviar
        sent = send_to_newsletter(content_id)
        result['sent'] = sent
        
    except Exception as e:
        result['error'] = str(e)
        result['trace'] = _tb.format_exc()
    
    return jsonify(result)
@require_admin
def dedup():
    """Remove duplicatas por URL, mantendo o mais antigo."""
    with get_db() as conn:
        cur = conn.cursor()
        if 'psycopg2' in str(type(conn)):
            cur.execute("""
                DELETE FROM content_items 
                WHERE id NOT IN (
                    SELECT MIN(id) FROM content_items GROUP BY url
                )
            """)
        else:
            cur.execute("""
                DELETE FROM content_items 
                WHERE id NOT IN (
                    SELECT MIN(id) FROM content_items GROUP BY url
                )
            """)
        removed = cur.rowcount
        conn.commit()
        return jsonify({'removed': removed})


@app.route('/api/clean-titles', methods=['POST'])
@require_admin
def clean_titles():
    """Limpa títulos existentes no banco usando SQL puro."""
    with get_db() as conn:
        cur = conn.cursor()
        # Remove flairs [P], [N], [D], [R] do final
        if 'psycopg2' in str(type(conn)):
            cur.execute("""
                UPDATE content_items SET title = regexp_replace(title, '\\s*\\[[A-Z]{1,3}\\]\\s*$', '', 'g')
                WHERE title ~ '\\s*\\[[A-Z]{1,3}\\]\\s*$'
            """)
            flairs = cur.rowcount
            cur.execute("""
                UPDATE content_items SET title = regexp_replace(title, '\\s*[/\\-|]\\s*$', '', 'g')
                WHERE title ~ '\\s*[/\\-|]\\s*$'
            """)
            trailing = cur.rowcount
        else:
            cur.execute("""
                UPDATE content_items SET title = rtrim(replace(replace(replace(title, ' [P]', ''), ' [N]', ''), ' [D]', ''), ' /-')
                WHERE title LIKE '%[P]' OR title LIKE '%[N]' OR title LIKE '%[D]' OR title LIKE '% /'
            """)
            flairs = cur.rowcount
            trailing = 0
        conn.commit()
        return jsonify({'cleaned': flairs + trailing})


@app.route('/content/<int:content_id>')
def content_detail(content_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cols = "id, title, url, source_name, source_type, category, summary, raw_content, published_at, fetched_at, analyzed, importance, metadata"
            if 'psycopg2' in str(type(conn)):
                cur.execute(f"SELECT {cols} FROM content_items WHERE id = %s", (content_id,))
            else:
                cur.execute(f"SELECT {cols} FROM content_items WHERE id = ?", (content_id,))
            item = cur.fetchone()
            if not item:
                return "Not found", 404
            
            if 'psycopg2' in str(type(conn)):
                cur.execute("SELECT id, content_id, expert_role, analysis, key_insights, relevance_score, created_at FROM content_analysis WHERE content_id = %s ORDER BY created_at DESC", (content_id,))
            else:
                cur.execute("SELECT id, content_id, expert_role, analysis, key_insights, relevance_score, created_at FROM content_analysis WHERE content_id = ? ORDER BY created_at DESC", (content_id,))
            analyses = [dict(row) for row in cur.fetchall()]
        
        return render_template('detail.html', item=dict(item), analyses=analyses)
    except Exception as e:
        return f"Erro: {e}", 500


# ── Health Endpoint ──────────────────────────────────────────────────

@app.route('/health')
def health():
    """Retorna saúde da aplicação em JSON."""
    stats = get_stats()
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - APP_START_TIME).total_seconds()
    return jsonify({
        'status': 'ok',
        'timestamp': now.isoformat(),
        'total_items': stats.get('total_items', 0),
        'analyzed_items': stats.get('analyzed_items', 0),
        'uptime_seconds': round(uptime_seconds, 1),
    })


# ── Batch Analyze via API ───────────────────────────────────────────

@app.route('/api/analyze-batch', methods=['POST'])
@require_admin
def api_analyze_batch():
    """Dispara análise em batch com rate limiting (1 chamada/minuto)."""
    global _last_analyze_call

    # Rate limit check
    now = datetime.now(timezone.utc)
    with _rate_limit_lock:
        if _last_analyze_call is not None:
            elapsed = (now - _last_analyze_call).total_seconds()
            if elapsed < 60:
                remaining = round(60 - elapsed)
                return jsonify({
                    'error': f'Rate limit: aguarde {remaining}s',
                    'retry_after': remaining,
                }), 429
        _last_analyze_call = now

    limit = request.args.get('limit', 50, type=int)
    from analyze_content import analyze_batch
    stats = analyze_batch(limit=limit)
    return jsonify({'success': True, 'stats': stats})


# ── Heartbeat via Telegram ──────────────────────────────────────────

@app.route('/api/heartbeat', methods=['GET'])
@require_admin
def api_heartbeat():
    """Envia heartbeat via Telegram com status do hub."""
    from distribute import send_heartbeat
    result = send_heartbeat()
    return jsonify({'success': True, 'result': result})


@app.route('/api/search', methods=['GET'])
def api_search():
    """Busca externa via search engines (Tavily + SearchAPI)."""
    try:
        return _api_search_impl()
    except Exception as e:
        import logging, traceback
        logging.error(f"api_search error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e), 'results': [], 'connectors': [], 'total': 0}), 500


def _api_search_impl():
    """Implementação da busca externa."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Parâmetro q é obrigatório'}), 400
    
    topic = request.args.get('topic', 'general')
    max_results = request.args.get('max_results', 5, type=int)
    save = request.args.get('save', 'true').lower() == 'true'
    
    # Busca nos conectores disponíveis
    _search_error = None
    _search_available = False
    connectors = []
    try:
        from search_engines.registry import get_registry
        registry = get_registry()
        connectors = registry.available()
        _search_available = True
    except Exception as _e:
        import logging
        _search_error = f"{type(_e).__name__}: {_e}"
        logging.error(f"search_engines error: {_search_error}")
    
    if not _search_available or not connectors:
        return jsonify({
            'query': query,
            'results': [],
            'saved': 0,
            'connectors': [c.name for c in connectors],
            'total': 0,
            'message': f'Search engines não disponível: {_search_error or "sem conectores ativos"}'
        })
    
    connector_names = [c.name for c in connectors]
    
    if not connectors:
        return jsonify({
            'query': query,
            'results': [],
            'saved': 0,
            'connectors': [],
            'total': 0,
            'message': 'Nenhum conector de busca disponível. Configure TAVILY_API_KEY ou SEARCHAPI_API_KEY.'
        })
    
    search_results_raw = registry.search_all(query, limit=max_results)
    search_results = [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "source_name": r.source,
            "published": r.published,
            "score": r.score,
        }
        for r in search_results_raw
    ]
    
    saved_count = 0
    if save and search_results:
        from database import save_content_items_batch, get_existing_urls
        from urllib.parse import urlparse
        
        hub_items = []
        for r in search_results:
            # Extrair domínio da URL como source_name (ex: "suno.com.br" em vez de "tavily")
            url = r.get('url', '')
            try:
                domain = urlparse(url).netloc.replace('www.', '')
            except:
                domain = r.get('source_name', 'search_engine')
            
            hub_items.append({
                'title': r['title'],
                'url': url,
                'source_name': domain if domain else r.get('source_name', 'search_engine'),
                'source_type': 'search_engine',
                'category': 'general',
                'summary': r.get('summary', ''),
                'raw_content': '',
                'published_at': r.get('published') or None,
                'metadata': json.dumps({'query': query, 'source': r.get('source_name', 'search')}),
            })
        
        if hub_items:
            existing = get_existing_urls([i['url'] for i in hub_items])
            new_items = [i for i in hub_items if i['url'] not in existing]
            if new_items:
                saved_count = save_content_items_batch(new_items)
    
    return jsonify({
        'query': query,
        'results': search_results,
        'saved': saved_count,
        'connectors': connector_names,
        'total': len(search_results) if search_results else 0
    })


# ── Main ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
