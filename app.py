#!/usr/bin/env python3
"""B2H4 Content Hub - Flask Dashboard.
Dashboard web para visualizar conteúdos coletados e analisados.
Reaproveita estrutura da newsletter.
"""

import os
import sys
import json
import random
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from database import get_db, get_stats, get_recent_items

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'b2h4-content-hub-dev')

@app.template_filter('fmt_date')
def fmt_date(dt):
    """Formata data para exibição. Funciona com string (SQLite) e datetime (PostgreSQL)."""
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
    """Dashboard principal."""
    stats = get_stats()
    recent = get_recent_items(hours=72)
    # Embaralha para mostrar mix de fontes
    random.shuffle(recent)
    recent = recent[:20]
    return render_template('index.html', stats=stats, items=recent)


@app.route('/api/stats')
def api_stats():
    """API: estatísticas gerais."""
    return jsonify(get_stats())


@app.route('/api/items')
def api_items():
    """API: lista de itens."""
    hours = request.args.get('hours', 24, type=int)
    category = request.args.get('category', None)
    items = get_recent_items(hours=hours, category=category)
    return jsonify({'items': items, 'count': len(items)})


@app.route('/api/trigger-fetch', methods=['POST'])
@require_admin
def trigger_fetch():
    """API: dispara coleta manual."""
    from fetch_sources import fetch_all_sources
    stats = fetch_all_sources()
    return jsonify(stats)


@app.route('/api/trigger-analyze', methods=['POST'])
@require_admin
def trigger_analyze():
    """API: dispara análise manual."""
    from analyze_content import analyze_batch
    limit = request.args.get('limit', 10, type=int)
    stats = analyze_batch(limit=limit)
    return jsonify(stats)


@app.route('/api/debug')
def debug():
    """Diagnóstico - verifica env vars disponíveis."""
    keys = ['OPENROUTER_API_KEY', 'DATABASE_URL', 'RESEND_API_KEY', 'TELEGRAM_BOT_TOKEN']
    result = {}
    for k in keys:
        v = os.environ.get(k, '')
        if v:
            result[k] = f"✓ configurada ({v[:8]}...{v[-4:]})"
        else:
            result[k] = "✗ NÃO configurada"
    return jsonify(result)


@app.route('/api/trigger-distribute', methods=['POST'])
@require_admin
def trigger_distribute():
    """API: dispara distribuição manual."""
    from distribute import send_daily_digest
    stats = send_daily_digest()
    return jsonify(stats)


@app.route('/content/<int:content_id>')
def content_detail(content_id):
    """Página de detalhe de um conteúdo."""
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
