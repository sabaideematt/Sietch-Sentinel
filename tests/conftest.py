"""Shared test fixtures."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure test environment doesn't touch real data
os.environ.setdefault("DATABASE_URL", "sqlite:///test_data/test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")  # Use DB 15 for tests
os.environ.setdefault("CHROMA_PERSIST_DIR", "./test_chroma_data")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test_sentinel.db"


@pytest.fixture
def sample_tle_lines():
    """ISS (ZARYA) TLE for testing."""
    return {
        "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9005",
        "line2": "2 25544  51.6400 208.9163 0006703 300.2578  59.7860 15.49560722999999",
    }


@pytest.fixture
def sample_tle_record(sample_tle_lines):
    """A TLERecord for testing."""
    from src.schemas import TLERecord

    return TLERecord(
        norad_cat_id=25544,
        object_name="ISS (ZARYA)",
        epoch=datetime(2024, 1, 1, 12, 0, 0),
        line1=sample_tle_lines["line1"],
        line2=sample_tle_lines["line2"],
        source="test",
    )


@pytest.fixture
def sample_tle_pair():
    """Two consecutive TLEs for delta-V testing."""
    from src.schemas import TLERecord

    tle1 = TLERecord(
        norad_cat_id=25544,
        object_name="ISS (ZARYA)",
        epoch=datetime(2024, 1, 1, 12, 0, 0),
        line1="1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9005",
        line2="2 25544  51.6400 208.9163 0006703 300.2578  59.7860 15.49560722999999",
        source="test",
    )
    tle2 = TLERecord(
        norad_cat_id=25544,
        object_name="ISS (ZARYA)",
        epoch=datetime(2024, 1, 2, 12, 0, 0),
        line1="1 25544U 98067A   24002.50000000  .00016717  00000-0  10270-3 0  9006",
        line2="2 25544  51.6400 208.9163 0006703 300.2578  59.7860 15.49560722999999",
        source="test",
    )
    return tle1, tle2


@pytest.fixture
def sample_delta_v():
    """A DeltaVEstimate for testing."""
    from src.schemas import DeltaVEstimate

    return DeltaVEstimate(
        norad_cat_id=25544,
        epoch_before=datetime(2024, 1, 1, 12, 0, 0),
        epoch_after=datetime(2024, 1, 2, 12, 0, 0),
        delta_v_m_s=1.5,
        uncertainty_m_s=0.15,
        confidence_interval=(1.35, 1.65),
    )


@pytest.fixture
def sample_anomaly_score(sample_delta_v):
    """An AnomalyScore for testing."""
    from src.schemas import AnomalyScore, AnomalySeverity

    return AnomalyScore(
        norad_cat_id=25544,
        timestamp=datetime.utcnow(),
        isolation_forest_score=0.7,
        lstm_reconstruction_error=0.8,
        composite_score=0.76,
        severity=AnomalySeverity.HIGH,
        delta_v=sample_delta_v,
    )


@pytest.fixture
def sample_investigation_result():
    """A complete InvestigationResult for testing."""
    from src.schemas import (
        InvestigationResult,
        OrbitRegime,
        DeltaVEstimate,
        TTPMatch,
        ConfidenceTier,
    )

    return InvestigationResult(
        investigation_id="test-inv-001",
        norad_cat_id=25544,
        satellite_name="ISS (ZARYA)",
        orbit_regime=OrbitRegime.LEO,
        anomaly_score=0.76,
        delta_v=DeltaVEstimate(
            norad_cat_id=25544,
            epoch_before=datetime(2024, 1, 1),
            epoch_after=datetime(2024, 1, 2),
            delta_v_m_s=1.5,
            uncertainty_m_s=0.15,
            confidence_interval=(1.35, 1.65),
        ),
        ttp_matches=[
            TTPMatch(
                framework="SPARTA",
                technique_id="EX-0001",
                technique_name="Unauthorized Commands",
                confidence=ConfidenceTier.MED,
                evidence_summary="Matched indicators: unexpected_delta_v",
                natural_cause_ruled_out=False,
            ),
        ],
        evidence_chain=["[space_weather] Kp=2 (quiet)", "[delta_v] 1.5 m/s detected"],
        tool_calls_used=5,
        tokens_used=3200,
        wall_clock_seconds=12.5,
        executive_summary="Anomalous delta-V detected on ISS. Space weather nominal. TTP match pending natural cause investigation.",
        recommended_actions=["Monitor for follow-up maneuver", "Check operator schedule"],
    )


@pytest.fixture
def memory_store(tmp_db):
    """A MemoryStore with an isolated temp database."""
    from src.memory.store import MemoryStore

    return MemoryStore(db_path=tmp_db)
