#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════════════
# Multi-Database & Multi-User Initialization for PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════
# This script creates separate databases and users for each project
# Run automatically on first container start via docker-entrypoint-initdb.d
# ═══════════════════════════════════════════════════════════════════════════

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- ═══════════════════════════════════════════════════════════════════════
    -- PROJECT: CHEAPA
    -- ═══════════════════════════════════════════════════════════════════════
    CREATE DATABASE cheapa_db;
    CREATE USER cheapa_user WITH ENCRYPTED PASSWORD '${CHEAPA_POSTGRES_PASSWORD:-changeme}';
    GRANT ALL PRIVILEGES ON DATABASE cheapa_db TO cheapa_user;
    
    \c cheapa_db
    GRANT ALL ON SCHEMA public TO cheapa_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO cheapa_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO cheapa_user;
    
    -- ═══════════════════════════════════════════════════════════════════════
    -- PROJECT: PROJECTB (Example)
    -- ═══════════════════════════════════════════════════════════════════════
    -- Uncomment when projectb is added:
    -- CREATE DATABASE projectb_db;
    -- CREATE USER projectb_user WITH ENCRYPTED PASSWORD '${PROJECTB_POSTGRES_PASSWORD:-changeme}';
    -- GRANT ALL PRIVILEGES ON DATABASE projectb_db TO projectb_user;
    
    -- \c projectb_db
    -- GRANT ALL ON SCHEMA public TO projectb_user;
    -- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO projectb_user;
    -- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO projectb_user;
    
EOSQL

echo "✅ Multi-database initialization complete"
echo "   - cheapa_db → cheapa_user"
echo "   - (add more projects above as needed)"

