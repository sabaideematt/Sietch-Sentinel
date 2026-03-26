"""SQLite backend — structured satellite profiles, maneuver history, feedback."""

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


class SQLiteBackend:
    """Structured storage for satellite profiles, investigations, and feedback."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.data_dir / "sietch_sentinel.db"
        self._init_tables()

    def _init_tables(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
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

                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    sync_status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    last_attempt TEXT,
                    created_at TEXT
                );
            """)
        logger.info("SQLite initialized at %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── Satellite Profiles ──

    def get_satellite_profile(self, norad_cat_id: int) -> Optional[SatelliteProfile]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM satellite_profiles WHERE norad_cat_id = ?",
                (norad_cat_id,),
            ).fetchone()
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
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
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

    # ── Investigations ──

    def log_investigation(self, norad_cat_id: int, data: dict) -> None:
        with self._connect() as conn:
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

    def get_investigation_norad_id(self, investigation_id: str) -> Optional[int]:
        """Look up the NORAD cat ID for a given investigation."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT norad_cat_id FROM investigations WHERE id = ?",
                (investigation_id,),
            ).fetchone()
        return row["norad_cat_id"] if row else None

    # ── Thresholds ──

    def update_thresholds(self, norad_cat_id: int, data: dict) -> None:
        with self._connect() as conn:
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

    # ── Analyst Feedback ──

    def get_analyst_feedback(
        self, norad_cat_id: int, investigation_id: str = ""
    ) -> list[AnalystFeedback]:
        with self._connect() as conn:
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
        norad_id = self.get_investigation_norad_id(feedback.investigation_id) or 0
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analyst_feedback
                   (feedback_id, investigation_id, norad_cat_id, analyst_id, verdict, notes, confidence_override, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feedback.feedback_id,
                    feedback.investigation_id,
                    norad_id,
                    feedback.analyst_id,
                    feedback.verdict.value,
                    feedback.notes,
                    feedback.confidence_override.value if feedback.confidence_override else None,
                    feedback.created_at.isoformat(),
                ),
            )
            conn.commit()

    def count_feedback_by_class(self) -> dict[str, int]:
        """Count labeled feedback per orbit regime for retraining threshold check."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT sp.orbit_regime, COUNT(*) as cnt
                   FROM analyst_feedback af
                   JOIN satellite_profiles sp ON af.norad_cat_id = sp.norad_cat_id
                   GROUP BY sp.orbit_regime""",
            ).fetchall()
        return {r["orbit_regime"]: r["cnt"] for r in rows}

    # ── Sync Log (for write-through consistency) ──

    def log_pending_sync(self, entity_type: str, entity_id: str) -> None:
        """Record that an entity needs to be synced to other backends."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sync_log (entity_type, entity_id, sync_status, created_at)
                   VALUES (?, ?, 'pending', ?)""",
                (entity_type, entity_id, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_pending_syncs(self) -> list[dict]:
        """Get all entities with pending sync status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sync_log WHERE sync_status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_synced(self, sync_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sync_log SET sync_status = 'synced', last_attempt = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), sync_id),
            )
            conn.commit()

    def mark_sync_failed(self, sync_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE sync_log
                   SET sync_status = 'pending', retry_count = retry_count + 1, last_attempt = ?
                   WHERE id = ?""",
                (datetime.utcnow().isoformat(), sync_id),
            )
            conn.commit()
