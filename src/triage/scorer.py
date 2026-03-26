"""Composite triage scorer — combines IF + LSTM scores, routes by severity."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import numpy as np

from src.schemas import (
    AnomalyScore,
    AnomalySeverity,
    DeltaVEstimate,
    OrbitRegime,
    SatelliteProfile,
)

logger = logging.getLogger(__name__)

# Default thresholds (overridden per-satellite from Memory Layer)
DEFAULT_THRESHOLDS = {
    OrbitRegime.GEO: {"low": 0.3, "high": 0.6},
    OrbitRegime.MEO: {"low": 0.35, "high": 0.65},
    OrbitRegime.LEO: {"low": 0.45, "high": 0.75},
    OrbitRegime.HEO: {"low": 0.4, "high": 0.7},
    OrbitRegime.UNKNOWN: {"low": 0.4, "high": 0.7},
}


class TriageScorer:
    """
    Merge Isolation Forest and LSTM scores into a composite anomaly score,
    apply uncertainty weighting, and route to severity tier.
    """

    def __init__(self, if_weight: float = 0.4, lstm_weight: float = 0.6):
        self.if_weight = if_weight
        self.lstm_weight = lstm_weight

    def compute(
        self,
        norad_cat_id: int,
        if_score: float,
        lstm_score: float,
        delta_v: Optional[DeltaVEstimate] = None,
        profile: Optional[SatelliteProfile] = None,
        orbit_regime: OrbitRegime = OrbitRegime.UNKNOWN,
    ) -> AnomalyScore:
        """Produce a single composite AnomalyScore with severity routing."""

        # Uncertainty weighting: boost score if delta-V uncertainty is low (high confidence)
        uncertainty_factor = 1.0
        if delta_v and delta_v.uncertainty_m_s > 0:
            # Lower uncertainty → higher confidence → higher effective score
            relative_uncertainty = delta_v.uncertainty_m_s / max(delta_v.delta_v_m_s, 1e-6)
            uncertainty_factor = max(0.5, 1.0 - relative_uncertainty)

        composite = (
            self.if_weight * if_score + self.lstm_weight * lstm_score
        ) * uncertainty_factor

        composite = float(np.clip(composite, 0.0, 1.0))

        # Determine thresholds
        if profile and profile.anomaly_threshold_low > 0:
            low_thresh = profile.anomaly_threshold_low
            high_thresh = profile.anomaly_threshold_high
        else:
            thresholds = DEFAULT_THRESHOLDS.get(orbit_regime, DEFAULT_THRESHOLDS[OrbitRegime.UNKNOWN])
            low_thresh = thresholds["low"]
            high_thresh = thresholds["high"]

        # Route severity
        if composite >= high_thresh:
            severity = AnomalySeverity.HIGH
        elif composite >= low_thresh:
            severity = AnomalySeverity.MID
        else:
            severity = AnomalySeverity.LOW

        return AnomalyScore(
            norad_cat_id=norad_cat_id,
            timestamp=datetime.utcnow(),
            isolation_forest_score=if_score,
            lstm_reconstruction_error=lstm_score,
            composite_score=composite,
            severity=severity,
            delta_v=delta_v,
        )

    @staticmethod
    def should_investigate(score: AnomalyScore) -> bool:
        """Only MID and HIGH pass to Layer 3 orchestrator."""
        return score.severity in (AnomalySeverity.MID, AnomalySeverity.HIGH)
