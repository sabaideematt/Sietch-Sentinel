"""Tests for Layer 4: Memory Layer — SQLite, Redis, ChromaDB, write-through."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas import (
    AnalystFeedback,
    FeedbackVerdict,
    ConfidenceTier,
    SatelliteProfile,
    OrbitRegime,
)


class TestSQLiteBackend:
    """SQLite structured storage tests."""

    def test_upsert_and_get_profile(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.upsert_satellite_profile(25544, {
            "object_name": "ISS (ZARYA)",
            "orbit_regime": "LEO",
            "operator": "NASA/Roscosmos",
            "typical_delta_v_m_s": 0.5,
            "maneuver_frequency_days": 14.0,
            "anomaly_threshold_low": 0.4,
            "anomaly_threshold_high": 0.75,
        })

        profile = db.get_satellite_profile(25544)
        assert profile is not None
        assert profile.norad_cat_id == 25544
        assert profile.object_name == "ISS (ZARYA)"
        assert profile.orbit_regime == OrbitRegime.LEO
        assert profile.operator == "NASA/Roscosmos"
        assert profile.typical_delta_v_m_s == 0.5

    def test_upsert_updates_existing(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.upsert_satellite_profile(25544, {"object_name": "ISS", "orbit_regime": "LEO"})
        db.upsert_satellite_profile(25544, {"object_name": "ISS (ZARYA)", "orbit_regime": "LEO"})

        profile = db.get_satellite_profile(25544)
        assert profile.object_name == "ISS (ZARYA)"

    def test_get_nonexistent_profile(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        assert db.get_satellite_profile(99999) is None

    def test_log_and_lookup_investigation(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.log_investigation(25544, {
            "investigation_id": "inv-001",
            "anomaly_score": 0.76,
            "executive_summary": "Test investigation",
            "evidence_chain": ["evidence 1"],
            "ttp_matches": [],
        })

        norad_id = db.get_investigation_norad_id("inv-001")
        assert norad_id == 25544

    def test_threshold_update(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.upsert_satellite_profile(25544, {"object_name": "ISS", "orbit_regime": "LEO"})
        db.update_thresholds(25544, {"low": 0.35, "high": 0.8})

        profile = db.get_satellite_profile(25544)
        assert profile.anomaly_threshold_low == 0.35
        assert profile.anomaly_threshold_high == 0.8

    def test_analyst_feedback_roundtrip(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.upsert_satellite_profile(25544, {"object_name": "ISS", "orbit_regime": "LEO"})
        db.log_investigation(25544, {"investigation_id": "inv-001", "anomaly_score": 0.5})

        feedback = AnalystFeedback(
            feedback_id="fb-001",
            investigation_id="inv-001",
            analyst_id="analyst-1",
            verdict=FeedbackVerdict.FALSE_POSITIVE,
            notes="Scheduled stationkeeping",
            confidence_override=ConfidenceTier.LOW,
        )
        db.save_analyst_feedback(feedback)

        results = db.get_analyst_feedback(25544, "inv-001")
        assert len(results) == 1
        assert results[0].verdict == FeedbackVerdict.FALSE_POSITIVE
        assert results[0].notes == "Scheduled stationkeeping"

    def test_sync_log(self, tmp_db):
        from src.memory.sqlite_backend import SQLiteBackend

        db = SQLiteBackend(tmp_db)
        db.log_pending_sync("profile", "25544")
        db.log_pending_sync("investigation_vector", "inv-001")

        pending = db.get_pending_syncs()
        assert len(pending) == 2
        assert pending[0]["entity_type"] == "profile"

        db.mark_synced(pending[0]["id"])
        remaining = db.get_pending_syncs()
        assert len(remaining) == 1


class TestMemoryStoreWriteThrough:
    """Write-through consistency tests using the unified MemoryStore."""

    def test_profile_write_through(self, memory_store):
        """Profile upsert should write to SQLite (Redis may not be available)."""
        memory_store.upsert_satellite_profile(25544, {
            "object_name": "ISS",
            "orbit_regime": "LEO",
        })
        profile = memory_store.get_satellite_profile(25544)
        assert profile is not None
        assert profile.object_name == "ISS"

    def test_investigation_write_through(self, memory_store):
        """Investigation log should write to SQLite and attempt ChromaDB index."""
        memory_store.log_investigation(25544, {
            "investigation_id": "inv-test",
            "anomaly_score": 0.8,
            "executive_summary": "Test anomaly on ISS detected unusual delta-V",
        })
        # Verify SQLite write
        norad_id = memory_store.sqlite.get_investigation_norad_id("inv-test")
        assert norad_id == 25544

    def test_reconcile_with_no_pending(self, memory_store):
        """Reconciliation with empty sync log should succeed."""
        results = memory_store.reconcile_pending_syncs()
        assert results["processed"] == 0
        assert results["succeeded"] == 0
        assert results["failed"] == 0
