# B2H4 Content Hub

AI-powered content intelligence platform. Coleta, analisa e distribui conteúdo usando 211 expert roles.

## Stack
- Python + Flask
- Supabase (PostgreSQL)
- Resend (Email)
- Telegram Bot
- Hermes Agent (expert analysis)

## Setup Local

```bash
cp .env.example .env
# Preencher DATABASE_URL, RESEND_API_KEY, TELEGRAM_BOT_TOKEN
pip install -r requirements.txt
python3 app.py
```

## API

- `GET /` — Dashboard
- `GET /api/stats` — Estatísticas
- `GET /api/items` — Lista de itens
- `POST /api/trigger-fetch?key=ADMIN_KEY` — Dispara coleta
- `POST /api/trigger-analyze?key=ADMIN_KEY` — Dispara análise
- `POST /api/trigger-distribute?key=ADMIN_KEY` — Dispara distribuição

## Fontes de Conteúdo (100% gratuitas)
- RSS Feeds (15+ fontes de tech/AI)
- arXiv API (papers acadêmicos)
- YouTube RSS (canais via feed XML)
- Hacker News API
- Reddit RSS (subreddits)
- GitHub Trending

## Custo
$0/mês — tudo gratuito.
