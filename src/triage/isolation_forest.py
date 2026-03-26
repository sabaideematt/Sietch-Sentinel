"""Isolation Forest detector for point anomalies per satellite class."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

from src.config import settings

logger = logging.getLogger(__name__)


class IsolationForestDetector:
    """
    Per-class Isolation Forest for detecting point anomalies in delta-V
    and orbital parameter feature vectors.
    """

    def __init__(self, contamination: float = 0.05, n_estimators: int = 200):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self._models: dict[str, IsolationForest] = {}

    def fit(self, orbit_class: str, features: np.ndarray) -> None:
        """Train an Isolation Forest for a given orbit class (e.g. 'GEO')."""
        model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(features)
        self._models[orbit_class] = model
        logger.info("Trained IsolationForest for class '%s' on %d samples", orbit_class, len(features))

    def score(self, orbit_class: str, features: np.ndarray) -> np.ndarray:
        """
        Return anomaly scores for feature vectors.
        Lower (more negative) = more anomalous.
        Normalized to [0, 1] where 1 = most anomalous.
        """
        model = self._models.get(orbit_class)
        if model is None:
            logger.warning("No model for class '%s'; returning zeros.", orbit_class)
            return np.zeros(len(features))

        raw_scores = model.decision_function(features)
        # Normalize: decision_function returns negative for anomalies
        # Map to [0, 1] where 1 = most anomalous
        normalized = 1.0 - (raw_scores - raw_scores.min()) / (raw_scores.ptp() + 1e-10)
        return normalized

    def save(self, orbit_class: str, path: Optional[Path] = None) -> Path:
        """Persist model to disk."""
        path = path or settings.models_dir / f"iforest_{orbit_class}.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._models[orbit_class], path)
        logger.info("Saved IsolationForest for '%s' to %s", orbit_class, path)
        return path

    def load(self, orbit_class: str, path: Optional[Path] = None) -> None:
        """Load model from disk."""
        path = path or settings.models_dir / f"iforest_{orbit_class}.joblib"
        if not path.exists():
            logger.warning("Model file not found: %s", path)
            return
        self._models[orbit_class] = joblib.load(path)
        logger.info("Loaded IsolationForest for '%s' from %s", orbit_class, path)

    @staticmethod
    def build_feature_vector(
        delta_v_m_s: float,
        uncertainty_m_s: float,
        semi_major_axis_km: float = 0.0,
        eccentricity: float = 0.0,
        inclination_deg: float = 0.0,
    ) -> np.ndarray:
        """Construct feature vector from orbital/maneuver parameters."""
        return np.array([
            delta_v_m_s,
            uncertainty_m_s,
            semi_major_axis_km,
            eccentricity,
            inclination_deg,
        ]).reshape(1, -1)
