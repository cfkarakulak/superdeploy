"""
Create processes table for storing app process definitions
"""

def up(conn):
    """Create processes table"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id SERIAL PRIMARY KEY,
            app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            command TEXT NOT NULL,
            replicas INTEGER DEFAULT 1,
            port INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(app_id, name)
        )
    """)
    
    # Create index for faster lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_processes_app_id ON processes(app_id)
    """)
    
    print("✅ Created processes table")

def down(conn):
    """Drop processes table"""
    conn.execute("DROP TABLE IF EXISTS processes CASCADE")
    print("✅ Dropped processes table")
