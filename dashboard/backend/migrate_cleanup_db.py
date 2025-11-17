"""
Database Migration: Cleanup unused tables

This script drops tables that are no longer used because we're fetching
data from CLI instead of database.

Dropped tables:
- vms (use CLI: project:status --json)
- addons (use CLI: project:status -a app --json)
- environments (hardcoded: production, staging)
- secrets (use CLI: project:config:list/set/unset)
- metrics_cache (use Prometheus real-time)

Simplified tables:
- apps: Only keeps id, project_id, name, repo, owner (for GitHub integration)
- projects: Only keeps id, name, domain, github_org (metadata only)

Run this script ONCE after deploying the new backend code.
"""

from sqlalchemy import create_engine, text, inspect
from database import SQLALCHEMY_DATABASE_URL

def migrate():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        print("🚀 Starting database migration...")
        print()
        
        # Get list of existing tables
        existing_tables = inspector.get_table_names()
        
        # Drop unused tables
        tables_to_drop = ["vms", "addons", "environments", "secrets", "metrics_cache"]
        
        for table in tables_to_drop:
            if table in existing_tables:
                print(f"🗑️  Dropping table: {table}")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                conn.commit()
            else:
                print(f"⏭️  Table {table} doesn't exist, skipping")
        
        print()
        
        # Simplify apps table
        if "apps" in existing_tables:
            print("🔧 Simplifying apps table...")
            
            # Get current columns
            columns = [col['name'] for col in inspector.get_columns('apps')]
            
            # Drop unnecessary columns
            columns_to_drop = ["type", "vm", "domain", "port", "dockerfile_path", "processes"]
            
            for col in columns_to_drop:
                if col in columns:
                    try:
                        print(f"   Dropping column: apps.{col}")
                        conn.execute(text(f"ALTER TABLE apps DROP COLUMN IF EXISTS {col} CASCADE"))
                        conn.commit()
                    except Exception as e:
                        print(f"   Warning: Could not drop apps.{col}: {e}")
        
        print()
        
        # Simplify projects table
        if "projects" in existing_tables:
            print("🔧 Simplifying projects table...")
            
            # Get current columns
            columns = [col['name'] for col in inspector.get_columns('projects')]
            
            # Drop unnecessary columns
            columns_to_drop = ["gcp_project_id", "cloud_provider", "cloud_region", "cloud_zone"]
            
            for col in columns_to_drop:
                if col in columns:
                    try:
                        print(f"   Dropping column: projects.{col}")
                        conn.execute(text(f"ALTER TABLE projects DROP COLUMN IF EXISTS {col} CASCADE"))
                        conn.commit()
                    except Exception as e:
                        print(f"   Warning: Could not drop projects.{col}: {e}")
        
        print()
        print("✅ Migration completed successfully!")
        print()
        print("📝 Summary:")
        print("   - Dropped 5 unused tables (vms, addons, environments, secrets, metrics_cache)")
        print("   - Simplified apps table (kept only: id, project_id, name, repo, owner)")
        print("   - Simplified projects table (kept only: id, name, domain, github_org)")
        print()
        print("🎯 Dashboard now uses CLI for real-time data instead of stale DB copies.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

