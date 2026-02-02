-- Enable pgvector extension for vector similarity search
-- This is used by the denial prevention system to store and query embeddings

-- Create the extension (idempotent - won't fail if already exists)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify it's installed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension is enabled';
    ELSE
        RAISE EXCEPTION 'pgvector extension failed to install';
    END IF;
END $$;
