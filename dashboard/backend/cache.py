"""Redis cache for SuperDeploy Dashboard."""

import redis
import json
from typing import Optional, Any

# Redis connection
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Cache TTL (Time To Live)
CACHE_TTL = {
    "projects": 300,  # 5 minutes
    "apps": 300,  # 5 minutes
    "vms": 300,  # 5 minutes
    "status": 60,  # 1 minute (for resources and metrics)
}


def get_cache(key: str) -> Optional[Any]:
    """Get value from cache."""
    try:
        value = redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None


def set_cache(key: str, value: Any, ttl: int = 300) -> bool:
    """Set value in cache with TTL."""
    try:
        redis_client.setex(key, ttl, json.dumps(value))
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False


def delete_cache(pattern: str) -> bool:
    """Delete cache keys matching pattern."""
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        return True
    except Exception as e:
        print(f"Cache delete error: {e}")
        return False


def clear_project_cache(project_name: str):
    """Clear all cache for a project."""
    delete_cache(f"project:{project_name}:*")
    delete_cache(f"apps:{project_name}:*")
    delete_cache(f"vms:{project_name}:*")
