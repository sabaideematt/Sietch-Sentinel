"""Tool 7: SPARTA + ATT&CK Matcher — Evidence-based dual-framework TTP scoring."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.schemas import ConfidenceTier, TTPMatch

# ── SPARTA TTP Catalog (space-specific) ──
SPARTA_TTPS = {
    "REC-0001": {"name": "Reconnaissance via RF Emissions", "indicators": ["unexpected_rf_change", "signal_anomaly"]},
    "IA-0001": {"name": "Compromise Ground Segment", "indicators": ["ground_access_anomaly", "uplink_anomaly"]},
    "IA-0002": {"name": "Compromise Space Vehicle", "indicators": ["unauthorized_maneuver", "telemetry_anomaly"]},
    "EX-0001": {"name": "Unauthorized Commands", "indicators": ["unexpected_delta_v", "off_schedule_maneuver"]},
    "EX-0002": {"name": "Payload Manipulation", "indicators": ["signal_degradation", "beam_pointing_change"]},
    "PER-0001": {"name": "Persistent Access via Firmware", "indicators": ["repeated_anomaly", "pattern_deviation"]},
    "DE-0001": {"name": "Orbital Denial of Service", "indicators": ["aggressive_maneuver", "proximity_approach"]},
    "EV-0001": {"name": "Evidence Destruction via Maneuver", "indicators": ["rapid_orbit_change", "deorbit_burn"]},
}

# ── MITRE ATT&CK TTPs (cyber, mapped to space context) ──
ATTACK_TTPS = {
    "T1059": {"name": "Command and Scripting Interpreter", "indicators": ["unauthorized_command", "uplink_anomaly"]},
    "T1071": {"name": "Application Layer Protocol", "indicators": ["comm_protocol_anomaly", "signal_anomaly"]},
    "T1485": {"name": "Data Destruction", "indicators": ["telemetry_loss", "rapid_orbit_change"]},
    "T1489": {"name": "Service Stop", "indicators": ["signal_loss", "transponder_off"]},
    "T1498": {"name": "Network Denial of Service", "indicators": ["jamming_detected", "signal_degradation"]},
    "T1557": {"name": "Adversary-in-the-Middle", "indicators": ["comm_intercept", "relay_anomaly"]},
    "T1562": {"name": "Impair Defenses", "indicators": ["sensor_degradation", "telemetry_anomaly"]},
}


class TTPMatcherInput(BaseModel):
    evidence_indicators: list[str] = Field(
        description="List of evidence indicator tags from the investigation"
    )
    natural_causes_ruled_out: bool = Field(
        default=False,
        description="Whether natural causes have been ruled out (required for HIGH confidence)",
    )


@tool("ttp_matcher", args_schema=TTPMatcherInput)
def ttp_matcher_tool(
    evidence_indicators: list[str],
    natural_causes_ruled_out: bool = False,
) -> str:
    """Match investigation evidence to SPARTA and MITRE ATT&CK TTPs.
    Requires natural causes to be ruled out before assigning HIGH confidence.
    Returns matched techniques with confidence tiers."""

    matches: list[TTPMatch] = []

    def _score(catalog: dict, framework: str):
        for tech_id, info in catalog.items():
            overlap = set(evidence_indicators) & set(info["indicators"])
            if not overlap:
                continue
            ratio = len(overlap) / len(info["indicators"])
            if ratio >= 0.75 and natural_causes_ruled_out:
                confidence = ConfidenceTier.HIGH
            elif ratio >= 0.5:
                confidence = ConfidenceTier.MED
            else:
                confidence = ConfidenceTier.LOW
            matches.append(TTPMatch(
                framework=framework,
                technique_id=tech_id,
                technique_name=info["name"],
                confidence=confidence,
                evidence_summary=f"Matched indicators: {', '.join(overlap)}",
                natural_cause_ruled_out=natural_causes_ruled_out,
            ))

    _score(SPARTA_TTPS, "SPARTA")
    _score(ATTACK_TTPS, "ATT&CK")

    if not matches:
        return "No TTP matches found for the provided evidence indicators."

    lines = [f"TTP Matches ({len(matches)} total):"]
    for m in sorted(matches, key=lambda x: x.confidence.value):
        lines.append(
            f"  [{m.framework}] {m.technique_id} — {m.technique_name}\n"
            f"    Confidence: {m.confidence.value} | {m.evidence_summary}\n"
            f"    Natural causes ruled out: {m.natural_cause_ruled_out}"
        )
    return "\n".join(lines)
