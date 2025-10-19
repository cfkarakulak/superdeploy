#!/usr/bin/env python3
"""
Proxy Registry Writer
Updates the proxy registry database with new proxy IPs
"""

import os
import sys
import json
import logging
from typing import List, Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://superdeploy:changeme123@localhost:5432/superdeploy_db"
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ProxyRegistry:
    """Proxy Registry Database Manager"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            logger.info("Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def init_table(self):
        """Initialize proxy registry table"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proxy_registry (
                    id SERIAL PRIMARY KEY,
                    ip VARCHAR(45) NOT NULL,
                    port INTEGER NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    last_seen TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    metadata JSONB,
                    UNIQUE(ip, port)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_status 
                ON proxy_registry(status)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_type 
                ON proxy_registry(type)
            """)

            self.conn.commit()
            logger.info("Proxy registry table initialized")

    def register_proxy(
        self,
        ip: str,
        port: int,
        proxy_type: str,
        status: str = "active",
        metadata: Optional[Dict] = None,
    ):
        """Register or update a proxy"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO proxy_registry (ip, port, type, status, last_seen, metadata)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (ip, port) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    last_seen = NOW(),
                    metadata = EXCLUDED.metadata
                RETURNING id
            """,
                (ip, port, proxy_type, status, json.dumps(metadata or {})),
            )

            proxy_id = cur.fetchone()[0]
            self.conn.commit()

            logger.info(
                f"Registered proxy: {ip}:{port} ({proxy_type}) - ID: {proxy_id}"
            )
            return proxy_id

    def get_active_proxies(self, proxy_type: Optional[str] = None) -> List[Dict]:
        """Get all active proxies"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if proxy_type:
                cur.execute(
                    """
                    SELECT * FROM proxy_registry 
                    WHERE status = 'active' AND type = %s
                    ORDER BY last_seen DESC
                """,
                    (proxy_type,),
                )
            else:
                cur.execute("""
                    SELECT * FROM proxy_registry 
                    WHERE status = 'active'
                    ORDER BY last_seen DESC
                """)

            return [dict(row) for row in cur.fetchall()]

    def mark_inactive(self, ip: str, port: int):
        """Mark proxy as inactive"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE proxy_registry 
                SET status = 'inactive'
                WHERE ip = %s AND port = %s
            """,
                (ip, port),
            )

            self.conn.commit()
            logger.info(f"Marked proxy as inactive: {ip}:{port}")

    def cleanup_old_proxies(self, hours: int = 24):
        """Remove proxies that haven't been seen in X hours"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM proxy_registry
                WHERE last_seen < NOW() - INTERVAL '%s hours'
            """,
                (hours,),
            )

            deleted_count = cur.rowcount
            self.conn.commit()

            logger.info(f"Cleaned up {deleted_count} old proxies")
            return deleted_count


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Proxy Registry Manager")
    parser.add_argument("--init", action="store_true", help="Initialize database table")
    parser.add_argument(
        "--register",
        nargs=3,
        metavar=("IP", "PORT", "TYPE"),
        help="Register a proxy (IP PORT TYPE)",
    )
    parser.add_argument("--list", action="store_true", help="List all active proxies")
    parser.add_argument(
        "--type", choices=["socks5", "http", "https"], help="Filter by proxy type"
    )
    parser.add_argument(
        "--cleanup", type=int, metavar="HOURS", help="Remove proxies older than X hours"
    )

    args = parser.parse_args()

    # Initialize registry
    registry = ProxyRegistry(DATABASE_URL)

    try:
        registry.connect()

        if args.init:
            registry.init_table()
            print("✅ Database table initialized")

        if args.register:
            ip, port, proxy_type = args.register
            proxy_id = registry.register_proxy(ip, int(port), proxy_type)
            print(f"✅ Registered proxy: {ip}:{port} ({proxy_type}) - ID: {proxy_id}")

        if args.list:
            proxies = registry.get_active_proxies(args.type)
            print(f"\n📋 Active Proxies ({len(proxies)}):")
            print("-" * 80)
            for proxy in proxies:
                print(
                    f"  {proxy['ip']}:{proxy['port']} ({proxy['type']}) - "
                    f"Last seen: {proxy['last_seen']}"
                )
            print()

        if args.cleanup:
            count = registry.cleanup_old_proxies(args.cleanup)
            print(f"✅ Cleaned up {count} old proxies")

        if not any([args.init, args.register, args.list, args.cleanup]):
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    finally:
        registry.close()


if __name__ == "__main__":
    main()
