#!/usr/bin/env python3
"""B2H4 Content Hub - Weekly Digest Generator.
Gera e envia resumo semanal dos melhores conteúdos.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from database import get_recent_items, get_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('weekly_digest')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'content@b2h4.ai')


def generate_weekly_digest(days: int = 7) -> Dict:
    """Gera digest semanal dos melhores conteúdos."""
    items = get_recent_items(hours=days * 24)
    
    if not items:
        return {'sent': False, 'reason': 'no_items'}
    
    # Agrupa por categoria
    by_category = {}
    for item in items:
        cat = item.get('category', 'general')
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    # Top 3 por categoria
    top_items = []
    for cat, cat_items in by_category.items():
        top_items.extend(cat_items[:3])
    
    # Ordena por importance
    top_items.sort(key=lambda x: x.get('importance', 0), reverse=True)
    top_items = top_items[:15]  # Top 15 geral
    
    stats = {
        'total_items': len(items),
        'by_category': {k: len(v) for k, v in by_category.items()},
        'top_items': len(top_items),
    }
    
    logger.info(f"Weekly digest: {stats}")
    return stats


if __name__ == '__main__':
    stats = generate_weekly_digest()
    print(json.dumps(stats, indent=2))
