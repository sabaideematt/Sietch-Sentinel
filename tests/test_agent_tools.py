"""Tests for Layer 3: Agent tools — basic invocation and schema validation."""

from __future__ import annotations

import pytest


class TestTTPMatcher:
    """TTP matcher tool tests."""

    def test_no_match_returns_message(self):
        from src.agent.tools.ttp_matcher import ttp_matcher_tool

        result = ttp_matcher_tool.invoke({
            "evidence_indicators": ["completely_unrelated_indicator"],
            "natural_causes_ruled_out": False,
        })
        assert "No TTP matches" in result

    def test_sparta_match(self):
        from src.agent.tools.ttp_matcher import ttp_matcher_tool

        result = ttp_matcher_tool.invoke({
            "evidence_indicators": ["unexpected_delta_v", "off_schedule_maneuver"],
            "natural_causes_ruled_out": False,
        })
        assert "SPARTA" in result
        assert "EX-0001" in result
        assert "Indicator score:" in result

    def test_high_confidence_requires_natural_cause_ruled_out(self):
        from src.agent.tools.ttp_matcher import ttp_matcher_tool

        # Without ruling out natural causes → should not be HIGH
        result_no_nc = ttp_matcher_tool.invoke({
            "evidence_indicators": ["unexpected_delta_v", "off_schedule_maneuver"],
            "natural_causes_ruled_out": False,
        })

        # With ruling out natural causes → can be HIGH
        result_with_nc = ttp_matcher_tool.invoke({
            "evidence_indicators": ["unexpected_delta_v", "off_schedule_maneuver"],
            "natural_causes_ruled_out": True,
        })

        assert "Natural causes ruled out: False" in result_no_nc
        assert "Natural causes ruled out: True" in result_with_nc

    def test_attack_match(self):
        from src.agent.tools.ttp_matcher import ttp_matcher_tool

        result = ttp_matcher_tool.invoke({
            "evidence_indicators": ["telemetry_loss", "rapid_orbit_change"],
            "natural_causes_ruled_out": False,
        })
        assert "ATT&CK" in result
        assert "T1485" in result


class TestOperatorSchedule:
    """Operator schedule tool tests."""

    def test_returns_no_schedule(self):
        from src.agent.tools.operator_schedule import operator_schedule_tool

        result = operator_schedule_tool.invoke({
            "norad_cat_id": 25544,
            "satellite_name": "ISS",
            "operator": "NASA",
        })
        assert "NO PUBLISHED SCHEDULE" in result
        assert "data gap" in result.lower()


class TestFleetCorrelator:
    """Fleet correlator tool tests."""

    def test_returns_no_data_when_unpopulated(self):
        from src.agent.tools.fleet_correlator import fleet_correlator_tool

        result = fleet_correlator_tool.invoke({
            "norad_cat_id": 25544,
            "operator": "NASA",
            "orbit_regime": "LEO",
        })
        assert "Fleet siblings found: 0" in result
