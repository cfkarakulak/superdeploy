/**
 * Frontend cache utility using localStorage with TTL
 */

interface CacheItem<T> {
  data: T;
  timestamp: number;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds

/**
 * Get data from cache
 */
export function getCache<T>(key: string): T | null {
  try {
    const item = localStorage.getItem(key);
    if (!item) return null;

    const cached: CacheItem<T> = JSON.parse(item);
    const now = Date.now();

    // Check if expired
    if (now - cached.timestamp > CACHE_TTL) {
      localStorage.removeItem(key);
      return null;
    }

    return cached.data;
  } catch (error) {
    console.error("Cache get error:", error);
    return null;
  }
}

/**
 * Set data in cache
 */
export function setCache<T>(key: string, data: T): void {
  try {
    const item: CacheItem<T> = {
      data,
      timestamp: Date.now(),
    };
    localStorage.setItem(key, JSON.stringify(item));
  } catch (error) {
    console.error("Cache set error:", error);
  }
}

/**
 * Clear specific cache key
 */
export function clearCache(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    console.error("Cache clear error:", error);
  }
}

/**
 * Clear all cache keys matching pattern
 */
export function clearCachePattern(pattern: string): void {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach((key) => {
      if (key.includes(pattern)) {
        localStorage.removeItem(key);
      }
    });
  } catch (error) {
    console.error("Cache clear pattern error:", error);
  }
}

