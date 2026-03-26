"""Tool 5: Conjunction Data — Space-Track CDM API, proximity events."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ConjunctionDataInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID of the primary satellite")
    days_back: int = Field(default=7, description="Days of CDM history to check")


@tool("conjunction_data", args_schema=ConjunctionDataInput)
def conjunction_data_tool(norad_cat_id: int, days_back: int = 7) -> str:
    """Check Space-Track Conjunction Data Messages (CDMs) for proximity events
    involving the target satellite. Helps distinguish evasive maneuvers from suspicious ones."""
    from src.config import settings

    if not settings.spacetrack_user or not settings.spacetrack_pass:
        return (
            "Space-Track credentials not configured. Cannot retrieve CDM data. "
            "Set SPACETRACK_USER and SPACETRACK_PASS in .env."
        )

    try:
        from spacetrack import SpaceTrackClient
        from datetime import datetime, timedelta

        st = SpaceTrackClient(
            identity=settings.spacetrack_user,
            password=settings.spacetrack_pass,
        )
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        cdms = st.cdm(
            norad_cat_id=norad_cat_id,
            creation_date=f">{since}",
            orderby="creation_date desc",
            limit=10,
            format="json",
        )

        import json
        data = json.loads(cdms) if isinstance(cdms, str) else cdms

        if not data:
            return f"No CDMs found for NORAD {norad_cat_id} in the last {days_back} days."

        lines = [f"Conjunction events for NORAD {norad_cat_id} ({len(data)} CDMs):"]
        for cdm in data[:5]:
            lines.append(
                f"  TCA: {cdm.get('TCA', 'N/A')} | "
                f"Miss distance: {cdm.get('MISS_DISTANCE', 'N/A')} km | "
                f"Probability: {cdm.get('COLLISION_PROBABILITY', 'N/A')} | "
                f"Secondary: {cdm.get('SAT_2_NAME', 'N/A')}"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"CDM retrieval failed: {e}"
