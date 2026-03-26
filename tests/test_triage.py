"""Tests for Layer 2: Triage ML — scoring and severity routing."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest


class TestIsolationForestDetector:
    """Isolation Forest anomaly detection tests."""

    def test_fit_and_score(self):
        from src.triage.isolation_forest import IsolationForestDetector

        detector = IsolationForestDetector(contamination=0.1, n_estimators=50)
        # Generate normal training data
        rng = np.random.RandomState(42)
        normal_data = rng.normal(loc=0, scale=1, size=(200, 5))
        detector.fit("GEO", normal_data)

        # Score normal data
        scores = detector.score("GEO", normal_data)
        assert scores.shape == (200,)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0

    def test_anomalous_data_scores_higher(self):
        from src.triage.isolation_forest import IsolationForestDetector

        detector = IsolationForestDetector(contamination=0.1, n_estimators=50)
        rng = np.random.RandomState(42)
        normal = rng.normal(loc=0, scale=1, size=(200, 5))
        detector.fit("GEO", normal)

        # Anomalous point: far from training distribution
        anomaly = np.array([[10.0, 10.0, 10.0, 10.0, 10.0]])
        anomaly_score = detector.score("GEO", anomaly)[0]

        normal_point = np.array([[0.0, 0.0, 0.0, 0.0, 0.0]])
        normal_score = detector.score("GEO", normal_point)[0]

        assert anomaly_score > normal_score

    def test_unknown_class_returns_zeros(self):
        from src.triage.isolation_forest import IsolationForestDetector

        detector = IsolationForestDetector()
        scores = detector.score("NONEXISTENT", np.zeros((5, 5)))
        assert np.all(scores == 0.0)

    def test_build_feature_vector(self):
        from src.triage.isolation_forest import IsolationForestDetector

        fv = IsolationForestDetector.build_feature_vector(
            delta_v_m_s=1.5, uncertainty_m_s=0.15,
            semi_major_axis_km=42164.0, eccentricity=0.001, inclination_deg=0.05,
        )
        assert fv.shape == (1, 5)


class TestTriageScorer:
    """Composite scoring and severity routing tests."""

    def test_low_scores_route_to_low_severity(self):
        from src.triage.scorer import TriageScorer
        from src.schemas import AnomalySeverity

        scorer = TriageScorer()
        result = scorer.compute(norad_cat_id=25544, if_score=0.1, lstm_score=0.1)
        assert result.severity == AnomalySeverity.LOW

    def test_high_scores_route_to_high_severity(self):
        from src.triage.scorer import TriageScorer
        from src.schemas import AnomalySeverity

        scorer = TriageScorer()
        result = scorer.compute(norad_cat_id=25544, if_score=0.9, lstm_score=0.9)
        assert result.severity == AnomalySeverity.HIGH

    def test_mid_scores_route_to_mid_severity(self):
        from src.triage.scorer import TriageScorer
        from src.schemas import AnomalySeverity, OrbitRegime

        scorer = TriageScorer()
        result = scorer.compute(
            norad_cat_id=25544, if_score=0.5, lstm_score=0.5,
            orbit_regime=OrbitRegime.GEO,
        )
        assert result.severity == AnomalySeverity.MID

    def test_should_investigate_mid_and_high_only(self):
        from src.triage.scorer import TriageScorer
        from src.schemas import AnomalyScore, AnomalySeverity

        scorer = TriageScorer()
        low = AnomalyScore(norad_cat_id=1, timestamp=datetime.utcnow(), severity=AnomalySeverity.LOW)
        mid = AnomalyScore(norad_cat_id=1, timestamp=datetime.utcnow(), severity=AnomalySeverity.MID)
        high = AnomalyScore(norad_cat_id=1, timestamp=datetime.utcnow(), severity=AnomalySeverity.HIGH)

        assert not scorer.should_investigate(low)
        assert scorer.should_investigate(mid)
        assert scorer.should_investigate(high)

    def test_uncertainty_weighting(self, sample_delta_v):
        from src.triage.scorer import TriageScorer

        scorer = TriageScorer()
        # High uncertainty should reduce effective score
        from src.schemas import DeltaVEstimate

        high_uncertainty = DeltaVEstimate(
            norad_cat_id=25544,
            epoch_before=sample_delta_v.epoch_before,
            epoch_after=sample_delta_v.epoch_after,
            delta_v_m_s=1.0,
            uncertainty_m_s=5.0,  # Very uncertain
            confidence_interval=(0.0, 6.0),
        )
        low_uncertainty = DeltaVEstimate(
            norad_cat_id=25544,
            epoch_before=sample_delta_v.epoch_before,
            epoch_after=sample_delta_v.epoch_after,
            delta_v_m_s=1.0,
            uncertainty_m_s=0.01,  # Very certain
            confidence_interval=(0.99, 1.01),
        )

        score_high_unc = scorer.compute(norad_cat_id=1, if_score=0.8, lstm_score=0.8, delta_v=high_uncertainty)
        score_low_unc = scorer.compute(norad_cat_id=1, if_score=0.8, lstm_score=0.8, delta_v=low_uncertainty)

        assert score_low_unc.composite_score >= score_high_unc.composite_score
