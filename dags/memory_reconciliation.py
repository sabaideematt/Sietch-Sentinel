"""
Airflow DAG: Nightly Memory Reconciliation

Repairs drift between the three memory backends (SQLite, Redis, ChromaDB)
by processing the sync_log table for pending entries.

Schedule: Daily at 02:00 UTC
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "sietch_sentinel",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def reconcile_pending_syncs(**kwargs):
    """Process all pending sync entries across memory backends."""
    from src.memory.store import MemoryStore

    store = MemoryStore()
    results = store.reconcile_pending_syncs()

    ti = kwargs.get("ti")
    if ti:
        ti.xcom_push(key="reconciliation_results", value=results)

    return results


def reindex_stale_investigations(**kwargs):
    """
    Re-index investigations in ChromaDB that may have drifted.
    Compares SQLite investigation count against ChromaDB document count
    and re-indexes any missing entries.
    """
    import sqlite3
    from src.memory.store import MemoryStore

    store = MemoryStore()
    chroma_count = store.chroma.count()

    with store.sqlite._connect() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM investigations").fetchone()
        sqlite_count = row["cnt"] if row else 0

    drift = sqlite_count - chroma_count
    reindexed = 0

    if drift > 0:
        with store.sqlite._connect() as conn:
            rows = conn.execute(
                """SELECT id, norad_cat_id, anomaly_score, executive_summary
                   FROM investigations
                   WHERE executive_summary IS NOT NULL AND executive_summary != ''
                   ORDER BY created_at DESC"""
            ).fetchall()

        for row in rows:
            success = store.chroma.index(
                doc_id=row["id"],
                text=row["executive_summary"],
                metadata={
                    "norad_cat_id": row["norad_cat_id"],
                    "anomaly_score": row["anomaly_score"],
                },
            )
            if success:
                reindexed += 1

    results = {
        "sqlite_count": sqlite_count,
        "chroma_count": chroma_count,
        "drift": drift,
        "reindexed": reindexed,
    }

    ti = kwargs.get("ti")
    if ti:
        ti.xcom_push(key="reindex_results", value=results)

    return results


def warm_redis_cache(**kwargs):
    """
    Pre-warm Redis cache with satellite profiles that have recent investigations.
    Reduces cold-start latency for the orchestrator agent.
    """
    from src.memory.store import MemoryStore

    store = MemoryStore()
    if not store.redis.available:
        return {"status": "redis_unavailable", "profiles_cached": 0}

    with store.sqlite._connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT sp.norad_cat_id
               FROM satellite_profiles sp
               JOIN investigations i ON sp.norad_cat_id = i.norad_cat_id
               ORDER BY i.created_at DESC
               LIMIT 100"""
        ).fetchall()

    cached = 0
    for row in rows:
        norad_id = row["norad_cat_id"]
        profile = store.sqlite.get_satellite_profile(norad_id)
        if profile:
            store.redis.cache_profile(norad_id, profile.model_dump_json())
            cached += 1

    results = {"status": "ok", "profiles_cached": cached}

    ti = kwargs.get("ti")
    if ti:
        ti.xcom_push(key="cache_warm_results", value=results)

    return results


with DAG(
    dag_id="sietch_sentinel_memory_reconciliation",
    default_args=default_args,
    description="Nightly reconciliation of SQLite ↔ Redis ↔ ChromaDB memory backends",
    schedule_interval="0 2 * * *",  # Daily at 02:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["sietch_sentinel", "memory", "maintenance"],
) as dag:

    t_reconcile = PythonOperator(
        task_id="reconcile_pending_syncs",
        python_callable=reconcile_pending_syncs,
    )

    t_reindex = PythonOperator(
        task_id="reindex_stale_investigations",
        python_callable=reindex_stale_investigations,
    )

    t_cache_warm = PythonOperator(
        task_id="warm_redis_cache",
        python_callable=warm_redis_cache,
    )

    # Reconcile first, then reindex, then warm cache
    t_reconcile >> t_reindex >> t_cache_warm
