# memory/

**Layer 4: Memory Layer — Three-Backend Store with Write-Through Consistency**

Provides persistent per-satellite knowledge using SQLite (source of truth), Redis (freshness-tagged cache), and ChromaDB (vector search). All writes go through a unified facade that ensures cross-backend consistency.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `MemoryStore`, `SQLiteBackend`, `RedisBackend`, `ChromaBackend` |
| `store.py` | `MemoryStore` — unified facade orchestrating write-through across all three backends. Write path: SQLite → Redis invalidation → ChromaDB index → `sync_log` on partial failure. Read path: Redis (if fresh) → SQLite fallback → cache warm on miss. Also exposes `reconcile_pending_syncs()` for the nightly Airflow DAG. |
| `sqlite_backend.py` | `SQLiteBackend` — structured storage for satellite profiles, investigations, analyst feedback, and the `sync_log` table for tracking pending cross-backend syncs. Source of truth for all data. |
| `redis_backend.py` | `RedisBackend` — live state cache with freshness-tagged envelopes. Every cached value includes a `fresh_at` timestamp. Provides `is_stale(key, max_age_seconds)` for staleness checks. Domain helpers for TLE cache, profile cache, and live investigation state. Degrades gracefully if Redis is unavailable. |
| `chroma_backend.py` | `ChromaBackend` — ChromaDB vector store for semantic similarity search over past investigation summaries. Uses cosine distance. Supports filtered queries by metadata (e.g., NORAD ID, anomaly score). |

## Consistency Model

```
WRITE PATH                          READ PATH
──────────                          ─────────
1. SQLite (source of truth)         1. Redis cache (if fresh)
2. Redis cache invalidation         2. SQLite fallback (if miss/stale)
3. ChromaDB vector index            3. Cache warm on miss
4. sync_log on failure              4. ChromaDB for semantic queries
```

Failed writes to Redis or ChromaDB are logged in the `sync_log` table and retried by the nightly Airflow DAG (`dags/memory_reconciliation.py`).
