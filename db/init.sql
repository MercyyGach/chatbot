-- Enable the pgvector extension (adds the `vector` data type + similarity search)
CREATE EXTENSION IF NOT EXISTS vector;

-- Raw scraped pages, one row per URL
CREATE TABLE IF NOT EXISTS pages (
    id          SERIAL PRIMARY KEY,
    site        TEXT NOT NULL,        -- e.g. 'advaforecourt', 'stationery', 'main'
    url         TEXT NOT NULL UNIQUE,
    title       TEXT,
    raw_text    TEXT NOT NULL,
    scraped_at  TIMESTAMP DEFAULT NOW()
);

-- Chunked text ready for embedding (embedding filled in during the next step)
CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    page_id     INTEGER REFERENCES pages(id) ON DELETE CASCADE,
    site        TEXT NOT NULL,
    url         TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    -- gemini-embedding-001 default output is 3072 dims;
    -- we'll use output_dimensionality=768 to keep storage/search cheap and fast
    embedding   vector(768),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Index for fast similarity search once embeddings are populated
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for filtering by site (your "pull site-specific info" requirement)
CREATE INDEX IF NOT EXISTS chunks_site_idx ON chunks (site);
