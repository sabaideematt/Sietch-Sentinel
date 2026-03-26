"""Unified Memory Store — wraps Redis (cache), SQLite (structured), ChromaDB (vector)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import settings
from src.schemas import AnalystFeedback, SatelliteProfile, OrbitRegime

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Unified interface to the three memory backends.

    - SQLite: satellite profiles, maneuver history, feedback
    - ChromaDB: vector store for semantic search over investigations
    - Redis: live state cache (optional, degrades gracefully)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.data_dir / "sietch_sentinel.db"
        self._init_sqlite()
        self._chroma_collection = None
        self._redis_client = None

    # ──────────────────── SQLite ────────────────────

    def _init_sqlite(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS satellite_profiles (
                norad_cat_id INTEGER PRIMARY KEY,
                object_name TEXT NOT NULL,
                orbit_regime TEXT DEFAULT 'UNKNOWN',
                operator TEXT DEFAULT '',
                launch_date TEXT,
                typical_delta_v_m_s REAL DEFAULT 0.0,
                maneuver_frequency_days REAL DEFAULT 0.0,
                anomaly_threshold_low REAL DEFAULT 0.0,
                anomaly_threshold_high REAL DEFAULT 1.0,
                total_investigations INTEGER DEFAULT 0,
                false_positive_count INTEGER DEFAULT 0,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                norad_cat_id INTEGER,
                anomaly_score REAL,
                executive_summary TEXT,
                evidence_chain TEXT,
                ttp_matches TEXT,
                created_at TEXT,
                FOREIGN KEY (norad_cat_id) REFERENCES satellite_profiles(norad_cat_id)
            );

            CREATE TABLE IF NOT EXISTS analyst_feedback (
                feedback_id TEXT PRIMARY KEY,
                investigation_id TEXT,
                norad_cat_id INTEGER,
                analyst_id TEXT DEFAULT '',
                verdict TEXT NOT NULL,
                notes TEXT DEFAULT '',
                confidence_override TEXT,
                created_at TEXT,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id)
            );
        """)
        conn.close()
        logger.info("SQLite initialized at %s", self.db_path)

    def get_satellite_profile(self, norad_cat_id: int) -> Optional[SatelliteProfile]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM satellite_profiles WHERE norad_cat_id = ?",
            (norad_cat_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return SatelliteProfile(
            norad_cat_id=row["norad_cat_id"],
            object_name=row["object_name"],
            orbit_regime=OrbitRegime(row["orbit_regime"]),
            operator=row["operator"],
            typical_delta_v_m_s=row["typical_delta_v_m_s"],
            maneuver_frequency_days=row["maneuver_frequency_days"],
            anomaly_threshold_low=row["anomaly_threshold_low"],
            anomaly_threshold_high=row["anomaly_threshold_high"],
            total_investigations=row["total_investigations"],
            false_positive_count=row["false_positive_count"],
        )

    def upsert_satellite_profile(self, norad_cat_id: int, data: dict) -> None:
        conn = sqlite3.connect(str(self.db_path))
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO satellite_profiles
                (norad_cat_id, object_name, orbit_regime, operator,
                 typical_delta_v_m_s, maneuver_frequency_days,
                 anomaly_threshold_low, anomaly_threshold_high, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(norad_cat_id) DO UPDATE SET
                 object_name = COALESCE(excluded.object_name, object_name),
                 orbit_regime = COALESCE(excluded.orbit_regime, orbit_regime),
                 operator = COALESCE(excluded.operator, operator),
                 typical_delta_v_m_s = COALESCE(excluded.typical_delta_v_m_s, typical_delta_v_m_s),
                 maneuver_frequency_days = COALESCE(excluded.maneuver_frequency_days, maneuver_frequency_days),
                 anomaly_threshold_low = COALESCE(excluded.anomaly_threshold_low, anomaly_threshold_low),
                 anomaly_threshold_high = COALESCE(excluded.anomaly_threshold_high, anomaly_threshold_high),
                 last_updated = ?
            """,
            (
                norad_cat_id,
                data.get("object_name", f"NORAD-{norad_cat_id}"),
                data.get("orbit_regime", "UNKNOWN"),
                data.get("operator", ""),
                data.get("typical_delta_v_m_s", 0.0),
                data.get("maneuver_frequency_days", 0.0),
                data.get("anomaly_threshold_low", 0.0),
                data.get("anomaly_threshold_high", 1.0),
                now,
            ),
        )
        conn.commit()
        conn.close()

    def log_investigation(self, norad_cat_id: int, data: dict) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT OR REPLACE INTO investigations
               (id, norad_cat_id, anomaly_score, executive_summary, evidence_chain, ttp_matches, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("investigation_id", ""),
                norad_cat_id,
                data.get("anomaly_score", 0.0),
                data.get("executive_summary", ""),
                json.dumps(data.get("evidence_chain", [])),
                json.dumps(data.get("ttp_matches", [])),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def update_thresholds(self, norad_cat_id: int, data: dict) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """UPDATE satellite_profiles
               SET anomaly_threshold_low = ?, anomaly_threshold_high = ?, last_updated = ?
               WHERE norad_cat_id = ?""",
            (
                data.get("low", 0.0),
                data.get("high", 1.0),
                datetime.utcnow().isoformat(),
                norad_cat_id,
            ),
        )
        conn.commit()
        conn.close()

    def get_analyst_feedback(
        self, norad_cat_id: int, investigation_id: str = ""
    ) -> list[AnalystFeedback]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        if investigation_id:
            rows = conn.execute(
                "SELECT * FROM analyst_feedback WHERE investigation_id = ? ORDER BY created_at DESC",
                (investigation_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM analyst_feedback WHERE norad_cat_id = ? ORDER BY created_at DESC LIMIT 20",
                (norad_cat_id,),
            ).fetchall()
        conn.close()
        return [
            AnalystFeedback(
                feedback_id=r["feedback_id"],
                investigation_id=r["investigation_id"],
                analyst_id=r["analyst_id"],
                verdict=r["verdict"],
                notes=r["notes"],
                confidence_override=r["confidence_override"],
                created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else datetime.utcnow(),
            )
            for r in rows
        ]

    def save_analyst_feedback(self, feedback: AnalystFeedback) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT OR REPLACE INTO analyst_feedback
               (feedback_id, investigation_id, norad_cat_id, analyst_id, verdict, notes, confidence_override, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feedback.feedback_id,
                feedback.investigation_id,
                0,  # TODO: extract from investigation
                feedback.analyst_id,
                feedback.verdict.value,
                feedback.notes,
                feedback.confidence_override.value if feedback.confidence_override else None,
                feedback.created_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    # ──────────────────── ChromaDB (Vector) ────────────────────

    def _get_chroma(self):
        """Lazy-init ChromaDB collection."""
        if self._chroma_collection is not None:
            return self._chroma_collection
        try:
            import chromadb

            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._chroma_collection = client.get_or_create_collection(
                name="investigations",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB collection initialized.")
        except ImportError:
            logger.warning("chromadb not installed — vector search disabled.")
        except Exception as e:
            logger.warning("ChromaDB init failed: %s", e)
        return self._chroma_collection

    def index_investigation(self, investigation_id: str, text: str, metadata: dict = None) -> None:
        coll = self._get_chroma()
        if coll is None:
            return
        coll.upsert(
            ids=[investigation_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def search_investigations(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        coll = self._get_chroma()
        if coll is None:
            return []
        results = coll.query(query_texts=[query], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        return list(zip(docs, distances))

    # ──────────────────── Redis (Cache) ────────────────────

    def _get_redis(self):
        """Lazy-init Redis client. Degrades gracefully if unavailable."""
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis as redis_lib

            self._redis_client = redis_lib.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            logger.info("Redis connection established.")
        except Exception as e:
            logger.warning("Redis unavailable — cache disabled: %s", e)
            self._redis_client = None
        return self._redis_client

    def cache_set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        r = self._get_redis()
        if r:
            try:
                r.setex(key, ttl_seconds, value)
            except Exception as e:
                logger.warning("Redis SET failed: %s", e)

    def cache_get(self, key: str) -> Optional[str]:
        r = self._get_redis()
        if r:
            try:
                return r.get(key)
            except Exception as e:
                logger.warning("Redis GET failed: %s", e)
        return None
