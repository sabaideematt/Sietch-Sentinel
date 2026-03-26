"""Tool 10: Memory Read/Write — Retrieve baselines, update profiles, log outcomes."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class MemoryReadInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID to look up")
    query: str = Field(default="", description="Semantic search query for past investigations")


class MemoryWriteInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID")
    update_type: str = Field(description="Type of update: 'profile', 'investigation', 'threshold'")
    data: str = Field(description="JSON-serialized data to write")


@tool("memory_read", args_schema=MemoryReadInput)
def memory_read_tool(norad_cat_id: int, query: str = "") -> str:
    """Read satellite profile, historical baselines, or semantically search
    past investigations from the Memory Layer."""
    from src.memory.store import MemoryStore

    store = MemoryStore()

    # Structured profile lookup
    profile = store.get_satellite_profile(norad_cat_id)
    parts = []
    if profile:
        parts.append(
            f"Satellite Profile for NORAD {norad_cat_id}:\n"
            f"  Name: {profile.object_name}\n"
            f"  Orbit: {profile.orbit_regime.value}\n"
            f"  Operator: {profile.operator or 'unknown'}\n"
            f"  Typical ΔV: {profile.typical_delta_v_m_s:.2f} m/s\n"
            f"  Maneuver freq: every {profile.maneuver_frequency_days:.1f} days\n"
            f"  Thresholds: low={profile.anomaly_threshold_low:.2f}, high={profile.anomaly_threshold_high:.2f}\n"
            f"  Investigations: {profile.total_investigations} (FP: {profile.false_positive_count})"
        )
    else:
        parts.append(f"No satellite profile found for NORAD {norad_cat_id}.")

    # Semantic search for past investigations
    if query:
        results = store.search_investigations(query, top_k=3)
        if results:
            parts.append(f"\nSemantic search results for '{query}':")
            for doc, score in results:
                parts.append(f"  [{score:.3f}] {doc[:200]}...")
        else:
            parts.append(f"\nNo past investigations match query: '{query}'")

    return "\n".join(parts)


@tool("memory_write", args_schema=MemoryWriteInput)
def memory_write_tool(norad_cat_id: int, update_type: str, data: str) -> str:
    """Write updated satellite profile, investigation outcome, or threshold
    adjustment to the Memory Layer."""
    import json
    from src.memory.store import MemoryStore

    store = MemoryStore()

    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Invalid JSON data: {e}"

    if update_type == "profile":
        store.upsert_satellite_profile(norad_cat_id, payload)
        return f"Updated satellite profile for NORAD {norad_cat_id}."
    elif update_type == "investigation":
        store.log_investigation(norad_cat_id, payload)
        return f"Logged investigation outcome for NORAD {norad_cat_id}."
    elif update_type == "threshold":
        store.update_thresholds(norad_cat_id, payload)
        return f"Updated anomaly thresholds for NORAD {norad_cat_id}."
    else:
        return f"Unknown update_type: '{update_type}'. Use 'profile', 'investigation', or 'threshold'."
