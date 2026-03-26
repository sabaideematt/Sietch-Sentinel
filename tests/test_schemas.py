"""Tests for shared Pydantic schemas — serialization, validation, completeness."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.schemas import (
    AnomalyScore,
    AnomalySeverity,
    AnalystFeedback,
    ConfidenceTier,
    DeltaVEstimate,
    FeedbackVerdict,
    InvestigationRequest,
    InvestigationResult,
    OrbitRegime,
    ResourceUsage,
    SatelliteProfile,
    SpaceWeatherContext,
    StateVector,
    TLERecord,
    TTPMatch,
)


class TestEnums:
    def test_orbit_regimes(self):
        assert OrbitRegime.GEO.value == "GEO"
        assert OrbitRegime.LEO.value == "LEO"
        assert OrbitRegime.MEO.value == "MEO"

    def test_severity_levels(self):
        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.MID.value == "mid"
        assert AnomalySeverity.HIGH.value == "high"

    def test_confidence_tiers(self):
        assert ConfidenceTier.HIGH.value == "HIGH"
        assert ConfidenceTier.MED.value == "MED"
        assert ConfidenceTier.LOW.value == "LOW"


class TestTLERecord:
    def test_serialization_roundtrip(self, sample_tle_record):
        json_str = sample_tle_record.model_dump_json()
        restored = TLERecord.model_validate_json(json_str)
        assert restored.norad_cat_id == sample_tle_record.norad_cat_id
        assert restored.line1 == sample_tle_record.line1


class TestDeltaVEstimate:
    def test_confidence_interval_order(self, sample_delta_v):
        assert sample_delta_v.confidence_interval[0] <= sample_delta_v.confidence_interval[1]

    def test_uncertainty_range_auto_populated(self, sample_delta_v):
        assert sample_delta_v.delta_v_uncertainty_range is not None
        assert sample_delta_v.delta_v_uncertainty_range == sample_delta_v.confidence_interval

    def test_serialization(self, sample_delta_v):
        data = json.loads(sample_delta_v.model_dump_json())
        assert "delta_v_m_s" in data
        assert "uncertainty_m_s" in data
        assert "confidence_interval" in data
        assert "delta_v_uncertainty_range" in data
        assert data["delta_v_uncertainty_range"] == list(data["confidence_interval"])


class TestInvestigationResult:
    def test_full_schema_fields(self, sample_investigation_result):
        data = json.loads(sample_investigation_result.model_dump_json())

        # All fields from the architecture doc must be present
        assert "investigation_id" in data
        assert "anomaly_score" in data
        assert "delta_v" in data
        assert data["delta_v"]["uncertainty_m_s"] is not None
        assert data["delta_v"]["confidence_interval"] is not None
        assert "ttp_matches" in data
        assert "evidence_chain" in data
        assert "data_gaps" in data
        assert "insufficient_data" in data
        assert "executive_summary" in data
        assert "recommended_actions" in data
        assert "tool_calls_used" in data
        assert "tokens_used" in data
        assert "wall_clock_seconds" in data

    def test_ttp_match_confidence_tiers(self, sample_investigation_result):
        for ttp in sample_investigation_result.ttp_matches:
            assert ttp.confidence in (ConfidenceTier.HIGH, ConfidenceTier.MED, ConfidenceTier.LOW)
            assert ttp.framework in ("SPARTA", "ATT&CK")
            assert isinstance(ttp.indicator_score, float)

    def test_investigation_budget_used_block(self):
        budget = ResourceUsage(
            tool_calls_used=8, tool_calls_max=15,
            tokens_used=4500, tokens_max=8000,
            wall_clock_seconds=42.3, wall_clock_max=90.0,
            budget_exhausted=False,
        )
        result = InvestigationResult(
            investigation_id="budget-test",
            norad_cat_id=25544,
            satellite_name="ISS",
            orbit_regime=OrbitRegime.LEO,
            anomaly_score=0.5,
            investigation_budget_used=budget,
        )
        data = json.loads(result.model_dump_json())
        assert "investigation_budget_used" in data
        assert data["investigation_budget_used"]["tool_calls_used"] == 8
        assert data["investigation_budget_used"]["tokens_max"] == 8000
        assert data["investigation_budget_used"]["budget_exhausted"] is False


class TestSpaceWeatherContext:
    def test_creation(self):
        sw = SpaceWeatherContext(
            kp_index=3.0,
            solar_flux_sfu=120.5,
            cme_events_nearby=0,
            geomagnetic_storm=False,
        )
        assert sw.kp_index == 3.0
        assert not sw.geomagnetic_storm

    def test_storm_threshold(self):
        # Kp >= 5 is typically storm level
        sw = SpaceWeatherContext(
            kp_index=6.0,
            solar_flux_sfu=180.0,
            cme_events_nearby=2,
            geomagnetic_storm=True,
        )
        assert sw.geomagnetic_storm


class TestSatelliteProfile:
    def test_default_thresholds(self):
        profile = SatelliteProfile(
            norad_cat_id=25544,
            object_name="ISS",
            orbit_regime=OrbitRegime.LEO,
        )
        assert profile.anomaly_threshold_low == 0.0
        assert profile.anomaly_threshold_high == 1.0
        assert profile.false_positive_count == 0
