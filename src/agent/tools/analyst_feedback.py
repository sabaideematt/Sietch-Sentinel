"""Tool 11: Analyst Feedback Reader — Human corrections, confidence overrides."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class AnalystFeedbackInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID")
    investigation_id: str = Field(default="", description="Specific investigation ID to check")


@tool("analyst_feedback_reader", args_schema=AnalystFeedbackInput)
def analyst_feedback_tool(norad_cat_id: int, investigation_id: str = "") -> str:
    """Read analyst feedback for a satellite or specific investigation.
    Returns verdicts, corrections, and confidence overrides that should
    inform the current investigation."""
    from src.memory.store import MemoryStore

    store = MemoryStore()
    feedback_list = store.get_analyst_feedback(norad_cat_id, investigation_id)

    if not feedback_list:
        return (
            f"No analyst feedback found for NORAD {norad_cat_id}"
            + (f" (investigation: {investigation_id})" if investigation_id else "")
            + "."
        )

    lines = [f"Analyst feedback for NORAD {norad_cat_id} ({len(feedback_list)} entries):"]
    for fb in feedback_list[:10]:
        lines.append(
            f"  Investigation: {fb.investigation_id}\n"
            f"    Verdict: {fb.verdict.value}\n"
            f"    Notes: {fb.notes or '(none)'}\n"
            f"    Confidence override: {fb.confidence_override.value if fb.confidence_override else 'N/A'}\n"
            f"    Date: {fb.created_at.isoformat()}"
        )
    return "\n".join(lines)
