"""Unified Memory Store — facade over SQLite, ChromaDB, and Redis with write-through consistency."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import settings
from src.memory.sqlite_backend import SQLiteBackend
from src.memory.redis_backend import RedisBackend
from src.memory.chroma_backend import ChromaBackend
from src.schemas import AnalystFeedback, SatelliteProfile

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Unified facade over three memory backends with write-through consistency.

    Write path (on investigation close):
      1. Write to SQLite (source of truth)
      2. Invalidate/update Redis cache
      3. Index into ChromaDB
      4. If step 2 or 3 fails → log to sync_log with "pending" status for retry

    Read path:
      1. Check Redis cache first (with freshness tag check)
      2. Fall back to SQLite if cache miss or stale
      3. Semantic queries go directly to ChromaDB
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.sqlite = SQLiteBackend(db_path)
        self.redis = RedisBackend()
        self.chroma = ChromaBackend()

    # ──────────────────── Read Operations ────────────────────

    def get_satellite_profile(self, norad_cat_id: int) -> Optional[SatelliteProfile]:
        """Read-through: Redis cache → SQLite fallback."""
        # Try cache first
        cached = self.redis.get_cached_profile(norad_cat_id)
        if cached is not None:
            try:
                return SatelliteProfile.model_validate_json(cached)
            except Exception:
                pass  # Corrupted cache, fall through to SQLite

        # SQLite is source of truth
        profile = self.sqlite.get_satellite_profile(norad_cat_id)

        # Warm cache on read
        if profile is not None:
            self.redis.cache_profile(norad_cat_id, profile.model_dump_json())

        return profile

    def search_investigations(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Semantic search over past investigations via ChromaDB."""
        results = self.chroma.search(query, top_k=top_k)
        return [(doc, dist) for doc, dist, _ in results]

    def get_analyst_feedback(
        self, norad_cat_id: int, investigation_id: str = ""
    ) -> list[AnalystFeedback]:
        return self.sqlite.get_analyst_feedback(norad_cat_id, investigation_id)

    # ──────────────────── Write Operations (write-through) ────────────────────

    def upsert_satellite_profile(self, norad_cat_id: int, data: dict) -> None:
        """Write-through: SQLite → Redis cache → sync log on failure."""
        # 1. SQLite (source of truth)
        self.sqlite.upsert_satellite_profile(norad_cat_id, data)

        # 2. Invalidate Redis cache
        try:
            profile = self.sqlite.get_satellite_profile(norad_cat_id)
            if profile:
                self.redis.cache_profile(norad_cat_id, profile.model_dump_json())
        except Exception as e:
            logger.warning("Redis cache update failed for profile %d: %s", norad_cat_id, e)
            self.sqlite.log_pending_sync("profile", str(norad_cat_id))

    def log_investigation(self, norad_cat_id: int, data: dict) -> None:
        """Write-through: SQLite → ChromaDB vector index → Redis cleanup."""
        investigation_id = data.get("investigation_id", "")

        # 1. SQLite
        self.sqlite.log_investigation(norad_cat_id, data)

        # 2. ChromaDB — index the executive summary for semantic search
        summary = data.get("executive_summary", "")
        if summary and investigation_id:
            try:
                self.chroma.index(
                    doc_id=investigation_id,
                    text=summary,
                    metadata={
                        "norad_cat_id": norad_cat_id,
                        "anomaly_score": data.get("anomaly_score", 0.0),
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as e:
                logger.warning("ChromaDB index failed for investigation %s: %s", investigation_id, e)
                self.sqlite.log_pending_sync("investigation_vector", investigation_id)

        # 3. Clear live investigation state from Redis
        if investigation_id:
            self.redis.clear_investigation_state(investigation_id)

    def update_thresholds(self, norad_cat_id: int, data: dict) -> None:
        """Write-through: SQLite → Redis invalidation."""
        self.sqlite.update_thresholds(norad_cat_id, data)

        # Invalidate cached profile so next read picks up new thresholds
        try:
            profile = self.sqlite.get_satellite_profile(norad_cat_id)
            if profile:
                self.redis.cache_profile(norad_cat_id, profile.model_dump_json())
        except Exception as e:
            logger.warning("Redis cache invalidation failed for %d: %s", norad_cat_id, e)
            self.sqlite.log_pending_sync("threshold", str(norad_cat_id))

    def save_analyst_feedback(self, feedback: AnalystFeedback) -> None:
        """Write feedback to SQLite."""
        self.sqlite.save_analyst_feedback(feedback)

    def index_investigation(self, investigation_id: str, text: str, metadata: dict = None) -> None:
        """Direct ChromaDB index (for backward compat)."""
        self.chroma.index(investigation_id, text, metadata)

    # ──────────────────── Sync / Reconciliation ────────────────────

    def reconcile_pending_syncs(self) -> dict:
        """
        Process all pending sync entries. Called by nightly Airflow DAG.
        Returns summary of results.
        """
        pending = self.sqlite.get_pending_syncs()
        results = {"processed": 0, "succeeded": 0, "failed": 0}

        for entry in pending:
            results["processed"] += 1
            try:
                self._retry_sync(entry)
                self.sqlite.mark_synced(entry["id"])
                results["succeeded"] += 1
            except Exception as e:
                logger.error("Sync retry failed for %s/%s: %s", entry["entity_type"], entry["entity_id"], e)
                self.sqlite.mark_sync_failed(entry["id"])
                results["failed"] += 1

        logger.info("Reconciliation complete: %s", results)
        return results

    def _retry_sync(self, entry: dict) -> None:
        """Retry a single pending sync operation."""
        entity_type = entry["entity_type"]
        entity_id = entry["entity_id"]

        if entity_type == "profile" or entity_type == "threshold":
            norad_cat_id = int(entity_id)
            profile = self.sqlite.get_satellite_profile(norad_cat_id)
            if profile:
                success = self.redis.cache_profile(norad_cat_id, profile.model_dump_json())
                if not success:
                    raise RuntimeError(f"Redis cache update failed for {entity_id}")

        elif entity_type == "investigation_vector":
            # Re-index from SQLite data
            with self.sqlite._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM investigations WHERE id = ?", (entity_id,)
                ).fetchone()
            if row and row["executive_summary"]:
                success = self.chroma.index(
                    doc_id=entity_id,
                    text=row["executive_summary"],
                    metadata={
                        "norad_cat_id": row["norad_cat_id"],
                        "anomaly_score": row["anomaly_score"],
                    },
                )
                if not success:
                    raise RuntimeError(f"ChromaDB index failed for {entity_id}")

    # ──────────────────── Cache Helpers (pass-through) ────────────────────

    def cache_set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        self.redis.set(key, value, ttl_seconds)

    def cache_get(self, key: str) -> Optional[str]:
        return self.redis.get(key)

    def _get_redis(self):
        """Expose redis client for config checks (backward compat)."""
        return self.redis._get_client()
