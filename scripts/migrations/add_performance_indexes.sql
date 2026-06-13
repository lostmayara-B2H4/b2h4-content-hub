-- Trigram index for text search
CREATE INDEX IF NOT EXISTS idx_content_items_title_trgm ON content_items USING gin(title gin_trgm_ops);
-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_content_items_importance_fetched ON content_items(importance DESC, fetched_at DESC);
-- Index for url lookups
CREATE INDEX IF NOT EXISTS idx_content_items_analyzed ON content_items(analyzed) WHERE analyzed = FALSE;
