-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable other useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE excel_unified_development TO excel_unified;

-- Create test database for Rails tests
CREATE DATABASE excel_unified_test WITH OWNER = excel_unified;
GRANT ALL PRIVILEGES ON DATABASE excel_unified_test TO excel_unified;