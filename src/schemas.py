"""Shared Pydantic models used across all layers."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──

class OrbitRegime(str, Enum):
    GEO = "GEO"
    MEO = "MEO"
    LEO = "LEO"
    HEO = "HEO"
    UNKNOWN = "UNKNOWN"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


class ConfidenceTier(str, Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class FeedbackVerdict(str, Enum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    NEEDS_CORRECTION = "needs_correction"
    ESCALATE = "escalate"


# ── Layer 1: Ingestion ──

class TLERecord(BaseModel):
    """A single Two-Line Element set."""
    norad_cat_id: int
    object_name: str
    epoch: datetime
    line1: str
    line2: str
    source: str = "space-track"


class StateVector(BaseModel):
    """Position + velocity at a given epoch."""
    norad_cat_id: int
    epoch: datetime
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]


class DeltaVEstimate(BaseModel):
    """Maneuver candidate derived from consecutive TLE pairs."""
    norad_cat_id: int
    epoch_before: datetime
    epoch_after: datetime
    delta_v_m_s: float
    uncertainty_m_s: float
    confidence_interval: tuple[float, float]


# ── Layer 2: Triage ──

class AnomalyScore(BaseModel):
    """Output of the triage ML models."""
    norad_cat_id: int
    timestamp: datetime
    isolation_forest_score: float = 0.0
    lstm_reconstruction_error: float = 0.0
    composite_score: float = 0.0
    severity: AnomalySeverity = AnomalySeverity.LOW
    delta_v: Optional[DeltaVEstimate] = None


# ── Layer 3: Agent ──

class InvestigationRequest(BaseModel):
    """Payload sent from Triage → Orchestrator."""
    investigation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly: AnomalyScore
    satellite_name: str = ""
    orbit_regime: OrbitRegime = OrbitRegime.UNKNOWN
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TTPMatch(BaseModel):
    """A matched technique from SPARTA or ATT&CK."""
    framework: str  # "SPARTA" or "ATT&CK"
    technique_id: str
    technique_name: str
    confidence: ConfidenceTier
    evidence_summary: str
    natural_cause_ruled_out: bool = False


class InvestigationResult(BaseModel):
    """Final output of a single investigation."""
    investigation_id: str
    norad_cat_id: int
    satellite_name: str
    orbit_regime: OrbitRegime
    anomaly_score: float
    delta_v: Optional[DeltaVEstimate] = None
    ttp_matches: list[TTPMatch] = []
    evidence_chain: list[str] = []
    data_gaps: list[str] = []
    tool_calls_used: int = 0
    tokens_used: int = 0
    wall_clock_seconds: float = 0.0
    insufficient_data: bool = False
    executive_summary: str = ""
    recommended_actions: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Layer 4: Memory ──

class SatelliteProfile(BaseModel):
    """Persistent per-satellite knowledge base entry."""
    norad_cat_id: int
    object_name: str
    orbit_regime: OrbitRegime
    operator: str = ""
    launch_date: Optional[datetime] = None
    typical_delta_v_m_s: float = 0.0
    maneuver_frequency_days: float = 0.0
    anomaly_threshold_low: float = 0.0
    anomaly_threshold_high: float = 1.0
    total_investigations: int = 0
    false_positive_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ── Layer 6: Feedback ──

class AnalystFeedback(BaseModel):
    """A single analyst review of an investigation."""
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    analyst_id: str = ""
    verdict: FeedbackVerdict
    notes: str = ""
    confidence_override: Optional[ConfidenceTier] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
