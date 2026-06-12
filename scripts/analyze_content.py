#!/usr/bin/env python3
"""B2H4 Content Hub - Expert Analysis Engine.
Analisa conteúdos usando expert roles do agency-agents-zh.
Usa Hermes CLI para análise.
"""

import os
import sys
import json
import logging
import subprocess
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(__file__))
from database import get_unanalyzed_items, mark_analyzed, save_analysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('analyze')

# Path dos expert roles
AGENTS_DIR = os.path.expanduser("~/.hermes/skills/agency-agents-zh")

# Mapeamento categoria → expert role (arquivos reais)
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
    """Carrega o conteúdo de um expert role."""
    path = os.path.join(AGENTS_DIR, role_file)
    if not os.path.exists(path):
        logger.warning(f"Role não encontrado: {path}, usando default")
        return "You are a specialized content analyst. Analyze the content and provide key insights."
    
    with open(path, 'r') as f:
        content = f.read()
    
    # Remove frontmatter se existir
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    
    return content[:3000]


def analyze_with_hermes(role_content: str, title: str, summary: str, url: str) -> Dict:
    """Analisa conteúdo usando Hermes CLI."""
    
    prompt = f"""You are: {role_content[:500]}

Analyze this content:
Title: {title}
URL: {url}
Summary: {summary[:300]}

Provide:
EXECUTIVE_SUMMARY: [2-3 sentence summary]
KEY_POINTS:
- [point 1]
- [point 2]
- [point 3]
RELEVANCE: [high/medium/low]
TAGS: [tag1, tag2, tag3]"""
    
    try:
        result = subprocess.run(
            ['hermes', 'chat', '--cli', prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout.strip()
        
        # Parse da resposta
        analysis = {
            'summary': '',
            'key_points': [],
            'relevance': 'medium',
            'tags': []
        }
        
        current_section = None
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('EXECUTIVE_SUMMARY:'):
                analysis['summary'] = line.split(':', 1)[1].strip()
                current_section = 'summary'
            elif line.startswith('KEY_POINTS:'):
                current_section = 'points'
            elif line.startswith('RELEVANCE:'):
                rel = line.split(':', 1)[1].strip().lower()
                analysis['relevance'] = 'high' if 'high' in rel else ('low' if 'low' in rel else 'medium')
                current_section = None
            elif line.startswith('TAGS:'):
                tags_str = line.split(':', 1)[1].strip()
                analysis['tags'] = [t.strip() for t in tags_str.split(',')]
                current_section = None
            elif line.startswith('- ') and current_section == 'points':
                analysis['key_points'].append(line[2:])
            elif current_section == 'summary' and line:
                analysis['summary'] += ' ' + line
        
        relevance_score = 80 if analysis['relevance'] == 'high' else (50 if analysis['relevance'] == 'medium' else 20)
        
        return {
            'analysis': output,
            'insights': analysis['key_points'],
            'relevance_score': relevance_score
        }
    except subprocess.TimeoutExpired:
        logger.error("Timeout na análise Hermes")
        return {'analysis': f'Analysis timeout for: {title}', 'insights': [], 'relevance_score': 50}
    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        return {'analysis': f'Auto-analysis: {title}', 'insights': [], 'relevance_score': 50}


def analyze_content_item(item: Dict) -> Optional[Dict]:
    """Analisa um content item com o expert role apropriado."""
    category = item.get('category', 'general')
    role_file = CATEGORY_ROLE_MAP.get(category, 'product/product-manager.md')
    role_content = load_expert_role(role_file)
    
    logger.info(f"Analisando [{item['id']}]: {item['title'][:50]}... [role: {role_file}]")
    
    result = analyze_with_hermes(
        role_content=role_content,
        title=item['title'],
        summary=item.get('summary', ''),
        url=item['url']
    )
    
    # Salva análise no banco
    save_analysis(
        content_id=item['id'],
        expert_role=role_file,
        analysis=result['analysis'],
        insights=result['insights'],
        relevance=result['relevance_score']
    )
    
    # Marca como analisado
    mark_analyzed(item['id'])
    
    return result


def analyze_batch(limit: int = 10) -> Dict:
    """Analisa um batch de conteúdos não analisados."""
    items = get_unanalyzed_items(limit)
    stats = {'analyzed': 0, 'errors': 0, 'by_category': {}}
    
    logger.info(f"Analisando {len(items)} items...")
    
    for item in items:
        try:
            result = analyze_content_item(item)
            stats['analyzed'] += 1
            cat = item.get('category', 'general')
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
            logger.info(f"  ✅ {item['title'][:50]}")
        except Exception as e:
            logger.error(f"Erro analisando {item.get('title', 'unknown')}: {e}")
            stats['errors'] += 1
    
    logger.info(f"Análise completa: {stats['analyzed']} analisados, {stats['errors']} erros")
    return stats


if __name__ == '__main__':
    stats = analyze_batch(limit=3)
    print(json.dumps(stats, indent=2))
