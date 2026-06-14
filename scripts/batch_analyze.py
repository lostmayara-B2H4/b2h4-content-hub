#!/usr/bin/env python3
"""Batch analyze de todos os content_items não analisados.
Usa OpenRouter API com rate limiting (2s entre chamadas).
Pode demorar ~12min para 248 items.
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_unanalyzed_items, mark_analyzed, save_analysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('batch_analyze')

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'openrouter/auto')
AGENTS_DIR = os.path.expanduser("~/.hermes/skills/agency-agents-zh")

CATEGORY_ROLE_MAP = {
    'engineering': 'engineering/engineering-ai-engineer.md',
    'marketing': 'marketing/marketing-content-creator.md',
    'finance': 'finance/finance-cfo-advisor.md',
    'research': 'academic/academic-researcher.md',
    'tools': 'engineering/engineering-backend-architect.md',
    'regulation': 'legal/legal-compliance.md',
    'general': 'product/product-manager.md',
}

def load_expert_role(role_file):
    if not os.path.exists(AGENTS_DIR):
        return "You are a specialized content analyst."
    path = os.path.join(AGENTS_DIR, role_file)
    if not os.path.exists(path):
        return "You are a specialized content analyst."
    with open(path, 'r') as f:
        content = f.read()
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    return content[:2000]

def analyze_one(title, url, summary, role_prompt):
    system_prompt = f"{role_prompt[:1000]}\n\nBe concise. Reply in English."
    prompt = f"Title: {title}\nURL: {url}\nSummary: {summary[:500]}\n\nProvide:\nEXECUTIVE_SUMMARY: [2-3 sentences]\nKEY_POINTS:\n- [point 1]\n- [point 2]\n- [point 3]\nRELEVANCE: [high/medium/low]\nTAGS: [tag1, tag2, tag3]"
    
    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': os.environ.get("BASE_URL", ""),
        },
        json={
            'model': OPENROUTER_MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 500,
        },
        timeout=60
    )
    
    if resp.status_code != 200:
        raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")
    
    data = resp.json()
    analysis = data['choices'][0]['message']['content']
    
    insights = []
    relevance = 50
    for line in analysis.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            insights.append(line[2:])
        if 'high' in line.lower() and 'relevance' in line.lower():
            relevance = 80
        elif 'low' in line.lower() and 'relevance' in line.lower():
            relevance = 20
    
    return {
        'analysis': analysis,
        'insights': insights[:5],
        'relevance_score': relevance
    }

def main():
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY não configurada!")
        sys.exit(1)
    
    BATCH_SIZE = 50
    DELAY_BETWEEN_CALLS = 2  # seconds
    total_analyzed = 0
    total_errors = 0
    by_category = {}
    
    logger.info("=== BATCH ANALYZE START ===")
    
    while True:
        items = get_unanalyzed_items(BATCH_SIZE)
        if not items:
            logger.info("Todos os items foram analisados!")
            break
        
        logger.info(f"Batch: {len(items)} items para analisar")
        
        for item in items:
            try:
                category = item.get('category', 'general')
                role_file = CATEGORY_ROLE_MAP.get(category, 'product/product-manager.md')
                role_content = load_expert_role(role_file)
                
                result = analyze_one(
                    title=item['title'],
                    url=item.get('url', ''),
                    summary=item.get('summary', ''),
                    role_prompt=role_content
                )
                
                save_analysis(
                    content_id=item['id'],
                    expert_role=role_file,
                    analysis=result['analysis'],
                    insights=result['insights'],
                    relevance=result['relevance_score']
                )
                mark_analyzed(item['id'])
                
                total_analyzed += 1
                by_category[category] = by_category.get(category, 0) + 1
                logger.info(f"  ✅ [{item['id']}] {item['title'][:60]}")
                
                # Rate limiting
                time.sleep(DELAY_BETWEEN_CALLS)
                
            except Exception as e:
                total_errors += 1
                logger.error(f"  ❌ [{item.get('id')}] {e}")
                time.sleep(5)  # espera mais em caso de erro
        
        logger.info(f"Batch completo. Total: {total_analyzed} OK, {total_errors} erros")
    
    stats = {
        'total_analyzed': total_analyzed,
        'total_errors': total_errors,
        'by_category': by_category,
    }
    logger.info(f"=== BATCH ANALYZE COMPLETE ===")
    logger.info(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))

if __name__ == '__main__':
    main()
