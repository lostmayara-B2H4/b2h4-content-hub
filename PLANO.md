# 🚀 Projeto B2H4: AI Content Intelligence Platform

**Status:** 📋 PLANEJADO — Aguardando aprovação
**Data:** 12/06/2026
**Stack:** Hermes Agent + MemOS + agentmemory + agency-agents + codegraph
**Estimativa:** 5-7 dias de trabalho
**Entrega:** Plataforma funcionando em produção (Render)
**Custo:** $0 — tudo gratuito

---

## 💡 O Que É

Um **hub de inteligência de conteúdo** que usa os 211 expert roles (agency-agents-zh) + memória persistente (MemOS/agentmemory) para:

1. **Monitorar** fontes gratuitas (RSS, arXiv, YouTube RSS, Hacker News, Reddit, GitHub trending)
2. **Analisar** cada conteúdo com o expert role apropriado (marketing, engineering, finance, etc.)
3. **Gerar** resumos, insights e recomendações personalizados
4. **Distribuir** via Telegram, email (Resend free tier) e dashboard web
5. **Aprender** com o tempo — memória persistente lembra o que você leu, curtiu e ignorou

**Diferencial:** Cada conteúdo é analisado por um "especialista virtual" do agency-agents-zh, não por um prompt genérico. Um artigo de engenharia é analisado pelo `engineering/architect.md`, um de marketing pelo `marketing/content-strategist.md`, etc.

**Memória:** MemOS + agentmemory lembram seus interesses, o que já leu, o que curtiu. Com o tempo, a curadoria fica cada vez melhor.

---

## 📐 Arquitetura

```
┌─────────────────────────────────────────────────────┐
│              CONTENT SOURCES (100% gratis)           │
│  RSS │ arXiv API │ YouTube RSS │ HN │ Reddit │ GitHub│
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              CONTENT INGESTION LAYER                 │
│  fetch_sources.py → normalize → deduplicate          │
│  Roda via cron job (Hermes cronalytics)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│            EXPERT ANALYSIS ENGINE                    │
│  Classifica conteúdo → seleciona expert role         │
│  agency-agents-zh role → analisa → gera insight      │
│  MemOS: lembra preferências e histórico              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              DISTRIBUTION LAYER                      │
│  Telegram bot │ Email (Resend free) │ Dashboard web  │
│  Hermes web-search-plus para busca em tempo real     │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Tasks (ordem de execução)

### Fase 1: Foundation (Dia 1-2)

- [ ] **T1.1** — Criar estrutura do projeto `~/b2h4-content-hub/`
- [ ] **T1.2** — Configurar Supabase (tabelas `content_items`, `content_analysis`, `user_preferences`)
- [ ] **T1.3** — Implementar `fetch_sources.py`:
  - RSS feeds (blogs, sites de notícias)
  - arXiv API (papers de IA, tech)
  - YouTube RSS (canais via `youtube.com/feeds/videos.xml?channel_id=XXX`)
  - Hacker News API (top stories)
  - Reddit RSS (subreddits relevantes)
  - GitHub trending (RSS)
- [ ] **T1.4** — Implementar deduplicação e normalização
- [ ] **T1.5** — Configurar cron job (busca a cada 2h, analisa a cada 4h)

### Fase 2: Expert Engine (Dia 2-3)

- [ ] **T2.1** — Implementar classificador de conteúdo (categoriza por tema: eng, marketing, finance, etc.)
- [ ] **T2.2** — Implementar router → seleciona expert role do agency-agents-zh
- [ ] **T2.3** — Implementar `analyze_content.py` (usa Hermes subagent com role)
- [ ] **T2.4** — Integrar MemOS (salva análises, aprende preferências)
- [ ] **T2.5** — Integrar agentmemory (memória de conteúdos lidos/ignorados)

### Fase 3: Distribution (Dia 3-4)

- [ ] **T3.1** — Implementar `send_telegram.py` (bot com Hermes)
- [ ] **T3.2** — Implementar `send_email.py` (Resend free tier, template HTML)
- [ ] **T3.3** — Implementar dashboard web (Flask, simples)
- [ ] **T3.4** — Implementar feedback loop (👍/👎 nos conteúdos)

### Fase 4: Intelligence (Dia 4-5)

- [ ] **T4.1** — Implementar weekly digest (resumo semanal dos melhores)
- [ ] **T4.2** — Implementar trending topics (o que está bombando)
- [ ] **T4.3** — Implementar "porque você deveria ler" (personalizado)
- [ ] **T4.4** — Integrar codegraph (se conteúdo for código/repo)

### Fase 5: Deploy (Dia 5-6)

- [ ] **T5.1** — Dockerfile + docker-compose
- [ ] **T5.2** — Deploy Render (web service + cron)
- [ ] **T5.3** — Configurar variáveis de ambiente
- [ ] **T5.4** — Testes end-to-end
- [ ] **T5.5** — Monitoramento (cronalytics dashboard)

---

## 🛠️ Tecnologias (100% gratuitas)

| Camada | Tecnologia | Custo |
|---|---|---|
| Runtime | Hermes Agent | $0 |
| Memória | MemOS (memtensor) + agentmemory | $0 |
| Expert Roles | agency-agents-zh (211 roles) | $0 |
| Search | web-search-plus | $0 |
| Cron | Hermes cron + cronalytics | $0 |
| Database | Supabase free tier | $0 |
| Email | Resend free tier (100/dia) | $0 |
| Telegram | Hermes Telegram gateway | $0 |
| Dashboard | Flask | $0 |
| Deploy | Render free tier | $0 |
| Code Intelligence | codegraph | $0 |
| Content Sources | RSS, arXiv, YouTube RSS, HN, Reddit, GitHub | $0 |

**Custo total: $0/mês**

---

## 📊 Resultado Esperado

Após 1 semana:
- ✅ Bot no Telegram entregando conteúdo curado por especialistas virtuais
- ✅ Email diário com digest personalizado
- ✅ Dashboard web com histórico e trending
- ✅ Memória que melhora com o tempo (sabe o que você gosta)
- ✅ 211 expert roles analisando conteúdo 24/7
- ✅ Custo: $0

---

## ✅ Aprovação

Para iniciar, preciso:
1. **Aprovação deste plano** (sim/não)
2. **OpenRouter API key** para MemOS (pode ser a mesma do Hermes — free tier)
3. **Supabase** — usar o mesmo projeto da newsletter?

**Com a aprovação, começo pela Fase 1 imediatamente.**
