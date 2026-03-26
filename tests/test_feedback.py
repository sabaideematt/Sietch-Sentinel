"""Tests for Layer 6: Analyst Feedback Loop."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas import AnalystFeedback, FeedbackVerdict, ConfidenceTier


class TestFeedbackHandler:
    """Feedback processing tests."""

    def test_submit_feedback(self, memory_store):
        from src.feedback.handler import FeedbackHandler

        handler = FeedbackHandler(store=memory_store)
        feedback = AnalystFeedback(
            feedback_id="fb-test-001",
            investigation_id="inv-001",
            analyst_id="analyst-1",
            verdict=FeedbackVerdict.CONFIRMED,
            notes="Confirmed unauthorized maneuver.",
        )

        result = handler.submit(feedback)
        assert "feedback_saved" in result["actions"]
        assert result["feedback_id"] == "fb-test-001"

    def test_false_positive_feedback(self, memory_store):
        from src.feedback.handler import FeedbackHandler

        handler = FeedbackHandler(store=memory_store)
        feedback = AnalystFeedback(
            feedback_id="fb-test-002",
            investigation_id="inv-002",
            analyst_id="analyst-1",
            verdict=FeedbackVerdict.FALSE_POSITIVE,
            notes="Scheduled stationkeeping.",
        )

        result = handler.submit(feedback)
        assert "feedback_saved" in result["actions"]

    def test_confidence_override_recorded(self, memory_store):
        from src.feedback.handler import FeedbackHandler

        handler = FeedbackHandler(store=memory_store)
        feedback = AnalystFeedback(
            feedback_id="fb-test-003",
            investigation_id="inv-003",
            analyst_id="analyst-2",
            verdict=FeedbackVerdict.NEEDS_CORRECTION,
            confidence_override=ConfidenceTier.LOW,
        )

        result = handler.submit(feedback)
        assert "confidence_override_recorded" in result["actions"]

    def test_feedback_stats_default(self, memory_store):
        from src.feedback.handler import FeedbackHandler

        handler = FeedbackHandler(store=memory_store)
        stats = handler.get_feedback_stats()
        assert "total_feedback" in stats
        assert stats["retrain_ready"] is False
