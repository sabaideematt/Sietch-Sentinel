# dags/

**Airflow DAGs for scheduled maintenance tasks.**

## Files

| File | Purpose |
|---|---|
| `memory_reconciliation.py` | **Nightly Memory Reconciliation DAG** — runs daily at 02:00 UTC. Repairs drift between the three memory backends (SQLite, Redis, ChromaDB) with three sequential tasks. |

## DAG: `sietch_sentinel_memory_reconciliation`

**Schedule:** `0 2 * * *` (daily at 02:00 UTC)

### Tasks

| Task | Description |
|---|---|
| `reconcile_pending_syncs` | Processes the `sync_log` table in SQLite for entries with `status='pending'`. Retries failed Redis cache updates and ChromaDB vector indexes. Marks entries as synced or increments retry count on failure. |
| `reindex_stale_investigations` | Compares SQLite investigation count against ChromaDB document count. Re-indexes any missing investigation summaries into the vector store to repair drift. |
| `warm_redis_cache` | Pre-warms the Redis cache with satellite profiles that have recent investigations (up to 100). Reduces cold-start latency for the orchestrator agent. |

### Task Dependencies

```
reconcile_pending_syncs → reindex_stale_investigations → warm_redis_cache
```
