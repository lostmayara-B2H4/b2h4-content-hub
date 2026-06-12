#!/usr/bin/env python3
"""B2H4 Content Hub - Flask Dashboard."""

import os
import sys
import json
import math
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from database import get_db, get_stats, get_recent_items, clean_title

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'b2h4-content-hub-dev')

@app.template_filter('fmt_date')
def fmt_date(dt):
    if dt is None:
        return ''
    if isinstance(dt, str):
        return dt[:16]
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y %H:%M')
    return str(dt)[:16]

ADMIN_KEY = os.environ.get('ADMIN_KEY', '1234')

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
    
    # Busca
    items = get_recent_items(hours=24*30, category=category, limit=1000)
    
    # Filtro por texto
    if query:
        items = [i for i in items if query.lower() in i.get('title', '').lower()]
    
    # Ordenação
    if sort == 'relevance':
        items.sort(key=lambda x: (1 if x.get('analyzed') else 0, x.get('importance', 0)), reverse=True)
    else:
        items.sort(key=lambda x: x.get('fetched_at', ''), reverse=True)
    
    # Paginação
    total = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    items_page = items[start:start + per_page]
    
    return render_template('index.html', 
                         stats=stats, 
                         items=items_page,
                         current_page=page,
                         total_pages=total_pages,
                         total_items=total,
                         per_page=per_page)


@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())


@app.route('/api/items')
def api_items():
    hours = request.args.get('hours', 24, type=int)
    category = request.args.get('category', None)
    query = request.args.get('q', '').strip()
    items = get_recent_items(hours=hours, category=category)
    if query:
        items = [i for i in items if query.lower() in i.get('title', '').lower()]
    return jsonify({'items': items, 'count': len(items)})


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
@app.route('/api/dedup', methods=['POST'])
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
            if 'psycopg2' in str(type(conn)):
                cur.execute("SELECT * FROM content_items WHERE id = %s", (content_id,))
            else:
                cur.execute("SELECT * FROM content_items WHERE id = ?", (content_id,))
            item = cur.fetchone()
            if not item:
                return "Not found", 404
            
            if 'psycopg2' in str(type(conn)):
                cur.execute("SELECT * FROM content_analysis WHERE content_id = %s ORDER BY created_at DESC", (content_id,))
            else:
                cur.execute("SELECT * FROM content_analysis WHERE content_id = ? ORDER BY created_at DESC", (content_id,))
            analyses = [dict(row) for row in cur.fetchall()]
        
        return render_template('detail.html', item=dict(item), analyses=analyses)
    except Exception as e:
        return f"Erro: {e}", 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
