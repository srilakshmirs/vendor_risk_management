-- Runs once on first container boot (Postgres docker-entrypoint convention).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy text search for vendor names
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid() if we need it
