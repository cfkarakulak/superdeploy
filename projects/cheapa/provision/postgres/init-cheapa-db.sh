#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════════════
# CHEAPA PROJECT - PostgreSQL Database Initialization
# ═══════════════════════════════════════════════════════════════════════════
# This script is written to /opt/superdeploy/shared/postgres/init.d/cheapa.sh
# PostgreSQL automatically runs it on first start
# ═══════════════════════════════════════════════════════════════════════════

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create database
    CREATE DATABASE cheapa_db;
    
    -- Create user
    CREATE USER cheapa_user WITH ENCRYPTED PASSWORD '${CHEAPA_POSTGRES_PASSWORD}';
    
    -- Grant privileges
    GRANT ALL PRIVILEGES ON DATABASE cheapa_db TO cheapa_user;
    
    -- Connect to database and set permissions
    \c cheapa_db
    GRANT ALL ON SCHEMA public TO cheapa_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO cheapa_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO cheapa_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO cheapa_user;
EOSQL

echo "✅ Cheapa database initialized: cheapa_db → cheapa_user"

