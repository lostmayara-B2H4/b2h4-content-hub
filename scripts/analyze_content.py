#!/usr/bin/env python3
"""B2H4 Content Hub - Expert Analysis Engine.
Analisa conteúdos usando OpenRouter API (funciona no Render, sem Hermes CLI).
"""

import os
import sys
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(__file__))
from database import get_unanalyzed_items, mark_analyzed, save_analysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('analyze')

# OpenRouter config
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'openrouter/auto')

# Path dos expert roles
AGENTS_DIR = os.path.expanduser("~/.hermes/skills/agency-agents-zh")

# Mapeamento categoria → expert role
CATEGORY_ROLE_MAP = {
    'engineering': 'engineering/engineering-ai-engineer.md',
    'marketing': 'marketing/marketing-content-creator.md',
    'finance': 'finance/finance-cfo-advisor.md',
    'research': 'academic/academic-researcher.md',
    'tools': 'engineering/engineering-backend-architect.md',
    'regulation': 'legal/legal-compliance.md',
    'general': 'product/product-manager.md',
}


def load_expert_role(role_file: str) -> str:
    """Carrega o prompt de um expert role."""
    if not os.path.exists(AGENTS_DIR):
        return "You are a specialized content analyst. Analyze the content and provide key insights."
    
    path = os.path.join(AGENTS_DIR, role_file)
    if not os.path.exists(path):
        logger.warning(f"Role não encontrado: {role_file}")
        return "You are a specialized content analyst. Analyze the content and provide key insights."
    
    with open(path, 'r') as f:
        content = f.read()
    
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    
    return content[:2000]


def analyze_with_openrouter(prompt: str, role_prompt: str) -> Dict:
    """Analisa conteúdo usando OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return {'analysis': 'OPENROUTER_API_KEY not configured', 'insights': [], 'relevance_score': 50}
    
    system_prompt = f"{role_prompt[:1000]}\n\nYou are analyzing content. Be concise and insightful."
    
    try:
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
                    {'role': 'user', 'content': f"Analyze this content:\n\n{prompt}"}
                ],
                'max_tokens': 500,
            },
            timeout=30
        )
        
        if resp.status_code != 200:
            logger.warning(f"OpenRouter API error: {resp.status_code}")
            return {'analysis': f'API error: {resp.status_code}', 'insights': [], 'relevance_score': 50}
        
        data = resp.json()
        analysis = data['choices'][0]['message']['content']
        
        # Parse basic structure
        insights = []
        relevance = 50
        for line in analysis.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                insights.append(line[2:])
            if 'high' in line.lower() and ('relevance' in line.lower() or 'relev' in line.lower()):
                relevance = 80
            elif 'low' in line.lower() and ('relevance' in line.lower() or 'relev' in line.lower()):
                relevance = 20
        
        return {
            'analysis': analysis,
            'insights': insights[:5],
            'relevance_score': relevance
        }
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return {'analysis': f'Error: {e}', 'insights': [], 'relevance_score': 50}


def analyze_content_item(item: Dict) -> Optional[Dict]:
    """Analisa um content item com o expert role apropriado."""
    category = item.get('category', 'general')
    role_file = CATEGORY_ROLE_MAP.get(category, 'product/product-manager.md')
    role_content = load_expert_role(role_file)
    
    logger.info(f"Analisando [{item['id']}]: {item['title'][:50]}... [role: {role_file}]")
    
    prompt = f"""Title: {item['title']}
URL: {item.get('url', '')}
Summary: {item.get('summary', '')[:500]}

Provide:
EXECUTIVE_SUMMARY: [2-3 sentence summary]
KEY_POINTS:
- [point 1]
- [point 2]
- [point 3]
RELEVANCE: [high/medium/low]
TAGS: [tag1, tag2, tag3]"""
    
    result = analyze_with_openrouter(prompt, role_content)
    
    save_analysis(
        content_id=item['id'],
        expert_role=role_file,
        analysis=result['analysis'],
        insights=result['insights'],
        relevance=result['relevance_score']
    )
    
    mark_analyzed(item['id'])
    return result


def analyze_batch(limit: int = 10) -> Dict:
    """Analisa um batch de conteúdos não analisados em paralelo."""
    items = get_unanalyzed_items(limit)
    stats = {'analyzed': 0, 'errors': 0, 'by_category': {}}

    logger.info(f"Analisando {len(items)} items...")

    def _analyze_one(item):
        """Analyze a single item. Returns (item, result, error)."""
        try:
            result = analyze_content_item(item)
            return (item, result, None)
        except Exception as e:
            return (item, None, e)

    # Parallel analysis with max 5 concurrent LLM calls
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_analyze_one, item): item for item in items}
        for future in as_completed(futures):
            item, result, error = future.result()
            if error:
                logger.error(f"Erro: {item.get('title', '')}: {error}")
                stats['errors'] += 1
            else:
                stats['analyzed'] += 1
                cat = item.get('category', 'general')
                stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
                logger.info(f"  ✅ {item['title'][:50]}")

    logger.info(f"Completa: {stats['analyzed']} analisados, {stats['errors']} erros")
    return stats


if __name__ == '__main__':
    stats = analyze_batch(limit=3)
    print(json.dumps(stats, indent=2))
