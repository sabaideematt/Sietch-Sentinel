"""Tests for Layer 5: Report Generator — JSON, NL brief, STIX output."""

from __future__ import annotations

import json

import pytest


class TestReportGenerator:
    """Report generation tests."""

    def test_json_report_is_valid(self, sample_investigation_result):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        json_str = gen.to_json(sample_investigation_result)

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["investigation_id"] == "test-inv-001"
        assert data["norad_cat_id"] == 25544
        assert data["anomaly_score"] == 0.76
        assert len(data["ttp_matches"]) == 1
        assert data["ttp_matches"][0]["framework"] == "SPARTA"

    def test_json_report_contains_required_fields(self, sample_investigation_result):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        data = json.loads(gen.to_json(sample_investigation_result))

        required_fields = [
            "investigation_id", "norad_cat_id", "satellite_name",
            "orbit_regime", "anomaly_score", "delta_v", "ttp_matches",
            "evidence_chain", "data_gaps", "tool_calls_used", "tokens_used",
            "wall_clock_seconds", "insufficient_data", "executive_summary",
            "recommended_actions", "created_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_json_delta_v_has_uncertainty(self, sample_investigation_result):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        data = json.loads(gen.to_json(sample_investigation_result))
        dv = data["delta_v"]

        assert "delta_v_m_s" in dv
        assert "uncertainty_m_s" in dv
        assert "confidence_interval" in dv
        assert len(dv["confidence_interval"]) == 2
        assert "delta_v_uncertainty_range" in dv
        assert dv["delta_v_uncertainty_range"] == dv["confidence_interval"]

    def test_json_ttp_match_has_confidence_tiers(self, sample_investigation_result):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        data = json.loads(gen.to_json(sample_investigation_result))
        ttp = data["ttp_matches"][0]

        assert "framework" in ttp
        assert "technique_id" in ttp
        assert "confidence" in ttp
        assert ttp["confidence"] in ["HIGH", "MED", "LOW"]
        assert "indicator_score" in ttp
        assert isinstance(ttp["indicator_score"], float)
        assert "evidence_summary" in ttp
        assert "natural_cause_ruled_out" in ttp

    def test_nl_brief_contains_key_sections(self, sample_investigation_result):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        brief = gen.to_nl_brief(sample_investigation_result)

        assert "# Sietch Sentinel" in brief
        assert "Investigation ID" in brief
        assert "25544" in brief
        assert "ISS (ZARYA)" in brief
        assert "Executive Summary" in brief
        assert "TTP Matches" in brief
        assert "SPARTA" in brief
        assert "Resource Usage" in brief

    def test_nl_brief_insufficient_data_flag(self):
        from src.reports.generator import ReportGenerator
        from src.schemas import InvestigationResult, OrbitRegime

        result = InvestigationResult(
            investigation_id="test-partial",
            norad_cat_id=99999,
            satellite_name="UNKNOWN-SAT",
            orbit_regime=OrbitRegime.UNKNOWN,
            anomaly_score=0.5,
            insufficient_data=True,
            executive_summary="Partial investigation.",
        )

        gen = ReportGenerator()
        brief = gen.to_nl_brief(result)
        assert "INSUFFICIENT DATA" in brief

    def test_save_reports_creates_files(self, sample_investigation_result, tmp_path):
        from src.reports.generator import ReportGenerator

        gen = ReportGenerator()
        paths = gen.save_reports(sample_investigation_result, output_dir=tmp_path)

        assert "json" in paths
        assert "markdown" in paths
        assert paths["json"].exists()
        assert paths["markdown"].exists()


class TestSTIXBuilder:
    """STIX 2.1 bundle generation tests."""

    def test_stix_bundle_structure(self, sample_investigation_result):
        try:
            from src.reports.stix_builder import STIXBundleBuilder
            import stix2
        except ImportError:
            pytest.skip("stix2 not installed")

        builder = STIXBundleBuilder()
        bundle = builder.build(sample_investigation_result)

        assert bundle.type == "bundle"
        assert len(bundle.objects) > 0

        # Should contain Identity, ObservedData, Indicator, Sighting, Relationship, Note
        types = {obj.type for obj in bundle.objects}
        assert "identity" in types
        assert "observed-data" in types

    def test_stix_bundle_serializes(self, sample_investigation_result):
        try:
            from src.reports.stix_builder import STIXBundleBuilder
        except ImportError:
            pytest.skip("stix2 not installed")

        builder = STIXBundleBuilder()
        bundle = builder.build(sample_investigation_result)

        serialized = bundle.serialize(pretty=True)
        data = json.loads(serialized)
        assert data["type"] == "bundle"
        assert "objects" in data
