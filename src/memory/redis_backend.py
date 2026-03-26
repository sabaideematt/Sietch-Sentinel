"""Redis backend — live investigation state cache, recent TLE data, freshness tags."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


class RedisBackend:
    """
    Redis-based live state cache with freshness tags.

    Every cached value is stored alongside a `_fresh_at` timestamp so the
    agent can determine when context is stale.

    Degrades gracefully if Redis is unavailable — all methods return None/False
    rather than raising.
    """

    TTL_TLE = 3600          # 1 hour for TLE data
    TTL_PROFILE = 86400     # 24 hours for satellite profiles
    TTL_INVESTIGATION = 600 # 10 minutes for live investigation state

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import redis as redis_lib
            self._client = redis_lib.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
            logger.info("Redis connection established.")
        except Exception as e:
            logger.warning("Redis unavailable — cache disabled: %s", e)
            self._client = None
        return self._client

    @property
    def available(self) -> bool:
        return self._get_client() is not None

    # ── Generic cache with freshness tags ──

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        """Set a value with TTL and freshness timestamp."""
        r = self._get_client()
        if not r:
            return False
        try:
            envelope = json.dumps({
                "value": value,
                "fresh_at": datetime.utcnow().isoformat(),
            })
            r.setex(key, ttl_seconds, envelope)
            return True
        except Exception as e:
            logger.warning("Redis SET failed for '%s': %s", key, e)
            return False

    def get(self, key: str) -> Optional[str]:
        """Get raw value (unwrapped from freshness envelope)."""
        r = self._get_client()
        if not r:
            return None
        try:
            raw = r.get(key)
            if raw is None:
                return None
            envelope = json.loads(raw)
            return envelope.get("value")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Redis GET failed for '%s': %s", key, e)
            return None

    def get_with_freshness(self, key: str) -> Optional[tuple[str, datetime]]:
        """Get value along with its freshness timestamp."""
        r = self._get_client()
        if not r:
            return None
        try:
            raw = r.get(key)
            if raw is None:
                return None
            envelope = json.loads(raw)
            fresh_at = datetime.fromisoformat(envelope["fresh_at"])
            return (envelope["value"], fresh_at)
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning("Redis GET (with freshness) failed for '%s': %s", key, e)
            return None

    def is_stale(self, key: str, max_age_seconds: int) -> bool:
        """Check if a cached value is older than max_age_seconds."""
        result = self.get_with_freshness(key)
        if result is None:
            return True  # Missing = stale
        _, fresh_at = result
        age = (datetime.utcnow() - fresh_at).total_seconds()
        return age > max_age_seconds

    def delete(self, key: str) -> bool:
        r = self._get_client()
        if not r:
            return False
        try:
            r.delete(key)
            return True
        except Exception as e:
            logger.warning("Redis DELETE failed for '%s': %s", key, e)
            return False

    # ── Domain-specific cache helpers ──

    def cache_tle(self, norad_cat_id: int, tle_json: str) -> bool:
        return self.set(f"tle:latest:{norad_cat_id}", tle_json, self.TTL_TLE)

    def get_cached_tle(self, norad_cat_id: int) -> Optional[str]:
        return self.get(f"tle:latest:{norad_cat_id}")

    def cache_profile(self, norad_cat_id: int, profile_json: str) -> bool:
        return self.set(f"profile:{norad_cat_id}", profile_json, self.TTL_PROFILE)

    def get_cached_profile(self, norad_cat_id: int) -> Optional[str]:
        return self.get(f"profile:{norad_cat_id}")

    def set_investigation_state(self, investigation_id: str, state_json: str) -> bool:
        return self.set(f"investigation:live:{investigation_id}", state_json, self.TTL_INVESTIGATION)

    def get_investigation_state(self, investigation_id: str) -> Optional[str]:
        return self.get(f"investigation:live:{investigation_id}")

    def clear_investigation_state(self, investigation_id: str) -> bool:
        return self.delete(f"investigation:live:{investigation_id}")
