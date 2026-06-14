#!/usr/bin/env python3
"""B2H4 Content Hub - Distribution Layer.
Envia conteúdo curado via Telegram e Email.
Reaproveita tokens e config da newsletter.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict

import requests

sys.path.insert(0, os.path.dirname(__file__))
from database import get_recent_items, get_db, get_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('distribute')

# Config via env (reaproveita newsletter)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'content@b2h4.ai')


def send_telegram_message(text: str, chat_id: str = None) -> bool:
    """Envia mensagem via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado")
        return False
    
    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID não configurado")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Erro Telegram: {e}")
        return False


def format_telegram_digest(items: List[Dict], title: str = "📰 Content Hub Digest") -> str:
    """Formata digest para Telegram."""
    lines = [f"<b>{title}</b>", f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>", ""]
    
    for i, item in enumerate(items[:10], 1):
        cat_emoji = {
            'engineering': '⚙️', 'marketing': '📈', 'finance': '💰',
            'research': '🔬', 'tools': '🛠️', 'regulation': '⚖️', 'general': '📄'
        }.get(item.get('category', 'general'), '📄')
        
        lines.append(f"{i}. {cat_emoji} <a href=\"{item['url']}\">{item['title'][:80]}</a>")
        if item.get('summary'):
            lines.append(f"   <i>{item['summary'][:100]}...</i>")
        lines.append("")
    
    lines.append(f"\n📊 <b>Total:</b> {len(items)} conteúdos | 🔗 b2h4.ai/content")
    return "\n".join(lines)


def send_email_digest(items: List[Dict], to_email: str) -> bool:
    """Envia digest via Resend."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY não configurado")
        return False
    
    html_items = ""
    for item in items[:10]:
        cat_emoji = {
            'engineering': '⚙️', 'marketing': '📈', 'finance': '💰',
            'research': '🔬', 'tools': '🛠️', 'regulation': '⚖️', 'general': '📄'
        }.get(item.get('category', 'general'), '📄')
        
        html_items += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">
                <a href="{item['url']}" style="color: #333; text-decoration: none; font-weight: bold;">
                    {cat_emoji} {item['title']}
                </a>
                <br><small style="color: #666;">{item.get('summary', '')[:120]}...</small>
                <br><small style="color: #999;">{item.get('source_name', '')}</small>
            </td>
        </tr>
        """
    
    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #333;">📰 B2H4 Content Hub</h1>
        <p style="color: #666;">{datetime.now().strftime('%d/%m/%Y %H:%M')} — {len(items)} conteúdos selecionados</p>
        <table style="width: 100%; border-collapse: collapse;">
            {html_items}
        </table>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
            B2H4 Content Hub — Inteligência de conteúdo com especialistas virtuais.
            <br><a href="#">Descadastrar</a>
        </p>
    </body>
    </html>
    """
    
    try:
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_API_KEY}'},
            json={
                'from': FROM_EMAIL,
                'to': to_email,
                'subject': f'📰 Content Hub — {len(items)} conteúdos ({datetime.now().strftime("%d/%m")})',
                'html': html
            },
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Erro Resend: {e}")
        return False


def send_daily_digest(hours: int = 24) -> Dict:
    """Envia digest diário via Telegram e Email."""
    result = get_recent_items(hours=hours)
    items = result[0] if isinstance(result, tuple) else result
    stats = {'telegram': False, 'email': False, 'items_count': len(items)}

    if not items:
        logger.info("Nenhum item recente para enviar")
        return stats

    # Telegram
    text = format_telegram_digest(items)
    stats['telegram'] = send_telegram_message(text)

    # Email (para cada subscriber ativo)
    if RESEND_API_KEY:
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT email FROM subscribers WHERE active = TRUE")
                subscribers = [row['email'] for row in cur.fetchall()]
            except:
                subscribers = []

        for email in subscribers[:50]:  # Limita a 50 por dia (free tier)
            send_email_digest(items, email)

    logger.info(f"Digest enviado: {stats}")
    return stats


def send_heartbeat() -> Dict:
    """Envia heartbeat via Telegram com status do Content Hub."""
    stats = get_stats()
    total = stats.get('total_items', 0)
    analyzed = stats.get('analyzed_items', 0)
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    message = f"🟢 B2H4 Hub OK — {total} items, {analyzed} analisados — {now}"
    sent = send_telegram_message(message)
    logger.info(f"Heartbeat enviado: {sent}")
    return {'sent': sent, 'message': message, 'total_items': total, 'analyzed_items': analyzed}


if __name__ == '__main__':
    stats = send_daily_digest()
    print(json.dumps(stats, indent=2))
