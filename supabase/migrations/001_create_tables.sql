-- B2H4 Content Hub - Supabase Migration
-- Reaproveita o mesmo projeto Supabase da newsletter

-- Tabela de conteúdos coletados
CREATE TABLE IF NOT EXISTS content_items (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL, -- 'rss', 'arxiv', 'youtube', 'hackernews', 'reddit', 'github'
    category TEXT, -- 'engineering', 'marketing', 'finance', 'research', 'tools', 'general'
    summary TEXT,
    raw_content TEXT,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    analyzed BOOLEAN DEFAULT FALSE,
    importance INTEGER DEFAULT 0, -- 0-10
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Tabela de análises feitas pelos expert roles
CREATE TABLE IF NOT EXISTS content_analysis (
    id BIGSERIAL PRIMARY KEY,
    content_id BIGINT REFERENCES content_items(id) ON DELETE CASCADE,
    expert_role TEXT NOT NULL, -- 'engineering/architect', 'marketing/content-strategist', etc.
    analysis TEXT NOT NULL,
    key_insights JSONB DEFAULT '[]'::jsonb,
    relevance_score INTEGER DEFAULT 0, -- 0-100
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de preferências de conteúdo dos usuários
CREATE TABLE IF NOT EXISTS content_preferences (
    id BIGSERIAL PRIMARY KEY,
    subscriber_id BIGINT REFERENCES subscribers(id) ON DELETE CASCADE,
    preferred_categories JSONB DEFAULT '[]'::jsonb,
    preferred_sources JSONB DEFAULT '[]'::jsonb,
    reading_history JSONB DEFAULT '[]'::jsonb, -- [{content_id, action: 'read'|'skip'|'like', timestamp}]
    feedback_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de distribuição (o que foi enviado para quem)
CREATE TABLE IF NOT EXISTS content_distribution (
    id BIGSERIAL PRIMARY KEY,
    content_id BIGINT REFERENCES content_items(id) ON DELETE CASCADE,
    subscriber_id BIGINT REFERENCES subscribers(id) ON DELETE CASCADE,
    channel TEXT NOT NULL, -- 'telegram', 'email'
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    opened BOOLEAN DEFAULT FALSE,
    clicked BOOLEAN DEFAULT FALSE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_content_items_source ON content_items(source_type, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_items_category ON content_items(category);
CREATE INDEX IF NOT EXISTS idx_content_items_analyzed ON content_items(analyzed) WHERE analyzed = FALSE;
CREATE INDEX IF NOT EXISTS idx_content_analysis_content ON content_analysis(content_id);
CREATE INDEX IF NOT EXISTS idx_content_preferences_subscriber ON content_preferences(subscriber_id);

-- RLS (Row Level Security) - mesma política da newsletter
ALTER TABLE content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_distribution ENABLE ROW LEVEL SECURITY;

-- Policies para service_role (acesso total via backend)
CREATE POLICY "service_role_all_content_items" ON content_items FOR ALL USING (true);
CREATE POLICY "service_role_all_content_analysis" ON content_analysis FOR ALL USING (true);
CREATE POLICY "service_role_all_content_preferences" ON content_preferences FOR ALL USING (true);
CREATE POLICY "service_role_all_content_distribution" ON content_distribution FOR ALL USING (true);
