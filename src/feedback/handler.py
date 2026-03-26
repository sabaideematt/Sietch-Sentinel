"""Analyst feedback handler — process verdicts, update memory, trigger retraining."""

from __future__ import annotations

import logging
from typing import Optional

from src.memory.store import MemoryStore
from src.schemas import (
    AnalystFeedback,
    FeedbackVerdict,
    SatelliteProfile,
)

logger = logging.getLogger(__name__)

# Minimum labeled examples per class before retraining
MIN_EXAMPLES_FOR_RETRAIN = 50


class FeedbackHandler:
    """
    Process analyst feedback:
    1. Persist to Memory Layer
    2. Update satellite profile (reduce repeat false positives)
    3. Accumulate for triage ML retraining
    4. Adjust TTP matcher indicator weights on consistent overrides
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()

    def submit(self, feedback: AnalystFeedback) -> dict:
        """Process a single piece of analyst feedback. Returns summary of actions taken."""
        actions = []

        # 1. Persist feedback
        self.store.save_analyst_feedback(feedback)
        actions.append("feedback_saved")

        # 2. Update satellite profile based on verdict
        profile = self._get_profile_for_investigation(feedback.investigation_id)
        if profile:
            if feedback.verdict == FeedbackVerdict.FALSE_POSITIVE:
                self._handle_false_positive(profile)
                actions.append("profile_updated_fp")
            elif feedback.verdict == FeedbackVerdict.CONFIRMED:
                self._handle_confirmed(profile)
                actions.append("profile_updated_confirmed")

        # 3. Check if retraining threshold is met
        retrain_ready = self._check_retrain_threshold()
        if retrain_ready:
            actions.append("retrain_threshold_met")
            logger.info("Retraining threshold reached — queue ML retraining job.")

        # 4. Check for consistent confidence overrides
        if feedback.confidence_override:
            actions.append("confidence_override_recorded")

        logger.info(
            "Feedback %s processed: verdict=%s, actions=%s",
            feedback.feedback_id,
            feedback.verdict.value,
            actions,
        )
        return {"feedback_id": feedback.feedback_id, "actions": actions}

    def _get_profile_for_investigation(self, investigation_id: str) -> Optional[SatelliteProfile]:
        """Look up the satellite profile associated with an investigation."""
        # In a full implementation, join investigations → satellite_profiles
        # For MVP, return None (requires investigation → norad_cat_id lookup)
        return None

    def _handle_false_positive(self, profile: SatelliteProfile) -> None:
        """Adjust profile to reduce repeat false positives."""
        profile.false_positive_count += 1
        # Widen thresholds slightly to reduce sensitivity
        profile.anomaly_threshold_low = min(1.0, profile.anomaly_threshold_low + 0.02)
        profile.anomaly_threshold_high = min(1.0, profile.anomaly_threshold_high + 0.01)
        self.store.upsert_satellite_profile(
            profile.norad_cat_id,
            {
                "object_name": profile.object_name,
                "orbit_regime": profile.orbit_regime.value,
                "anomaly_threshold_low": profile.anomaly_threshold_low,
                "anomaly_threshold_high": profile.anomaly_threshold_high,
            },
        )
        logger.info(
            "FP adjustment for NORAD %d: thresholds → [%.2f, %.2f]",
            profile.norad_cat_id,
            profile.anomaly_threshold_low,
            profile.anomaly_threshold_high,
        )

    def _handle_confirmed(self, profile: SatelliteProfile) -> None:
        """Record confirmed anomaly in profile."""
        profile.total_investigations += 1
        self.store.upsert_satellite_profile(
            profile.norad_cat_id,
            {
                "object_name": profile.object_name,
                "orbit_regime": profile.orbit_regime.value,
            },
        )

    def _check_retrain_threshold(self) -> bool:
        """Check if enough labeled feedback has accumulated to trigger retraining."""
        # In a full implementation, count labeled examples per orbit class
        # For MVP, return False
        return False

    def get_feedback_stats(self) -> dict:
        """Return aggregate feedback statistics for monitoring."""
        # Placeholder — would query analyst_feedback table with GROUP BY
        return {
            "total_feedback": 0,
            "confirmed": 0,
            "false_positive": 0,
            "needs_correction": 0,
            "escalated": 0,
            "retrain_ready": False,
        }
