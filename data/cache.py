"""cache.py — Lightweight file-based JSON cache for expensive API calls.

Stores each cache entry as a separate JSON file in the project's cache/ directory.
The filename is the MD5 hash of the cache key so keys can be arbitrary strings.

Two TTL strategies used across the project:
  - Stock data (get_stock_snapshot):  15 minutes (prices don't change that fast)
  - News briefing (analyze_headlines): keyed by today's date so it auto-expires
    at midnight without needing a long TTL

Usage:
    from data.cache import cache_get, cache_set

    data = cache_get("stock_RELIANCE", ttl_seconds=900)
    if data is None:
        data = fetch_from_api()
        cache_set("stock_RELIANCE", data)
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_CACHE_DIR = Path(__file__).parent.parent / "cache"

# Convenience constants — import these in callers instead of hardcoding numbers
STOCK_TTL  = 15 * 60       # 15 minutes
NEWS_TTL   = 24 * 60 * 60  # 24 hours (news is also keyed by date, so this is a backstop)


def _key_to_path(key: str) -> Path:
    """Convert an arbitrary cache key string to a stable filename via MD5 hash."""
    filename = hashlib.md5(key.encode("utf-8")).hexdigest() + ".json"
    return _CACHE_DIR / filename


def cache_get(key: str, ttl_seconds: int):
    """
    Return cached data for `key` if it exists and hasn't expired.

    Args:
        key:         Cache key string, e.g. "stock_RELIANCE" or "news_2026-05-14"
        ttl_seconds: Maximum age of a valid cache entry in seconds.

    Returns:
        The cached data object (dict, list, str, etc.) if fresh, or None if the
        key doesn't exist, has expired, or the cache file is corrupt/unreadable.
    """
    path = _key_to_path(key)
    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(entry["timestamp"])
        age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
        if age_seconds > ttl_seconds:
            return None  # Stale — treat as miss
        return entry["data"]
    except Exception:
        # Corrupt file, missing keys, bad timestamp — treat as cache miss
        return None


def cache_set(key: str, data) -> None:
    """
    Store `data` in the cache under `key` with the current UTC timestamp.

    Creates the cache/ directory if it doesn't exist. Non-JSON-serializable
    values (e.g. datetime objects) are converted to strings via default=str.

    Args:
        key:  Cache key string.
        data: Data to cache. Should be JSON-serializable (dict, list, str, number, None).
    """
    _CACHE_DIR.mkdir(exist_ok=True)
    path = _key_to_path(key)
    entry = {
        "key":       key,       # Stored for human readability when debugging cache files
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data":      data,
    }
    path.write_text(
        json.dumps(entry, default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
