"""Tool 8: Operator Schedule Check — Published maneuver logs (opportunistic)."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class OperatorScheduleInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID")
    satellite_name: str = Field(default="", description="Satellite name for log lookup")
    operator: str = Field(default="", description="Operator name (e.g. 'Intelsat', 'SES')")


@tool("operator_schedule_check", args_schema=OperatorScheduleInput)
def operator_schedule_tool(
    norad_cat_id: int,
    satellite_name: str = "",
    operator: str = "",
) -> str:
    """Check for published operator maneuver schedules. Limited availability —
    treated as opportunistic data. Helps distinguish planned stationkeeping
    from unauthorized maneuvers."""
    # NOTE: No universal API for operator schedules. This is a placeholder
    # that would be populated from operator-specific feeds, ITU filings,
    # or manual data entry by analysts.

    return (
        f"Operator schedule check for NORAD {norad_cat_id} "
        f"({satellite_name or 'unknown'}, operator: {operator or 'unknown'}):\n"
        f"  Status: NO PUBLISHED SCHEDULE AVAILABLE\n"
        f"  Note: Operator maneuver logs are not universally published. "
        f"This data source is opportunistic. Absence of a published schedule "
        f"does NOT indicate an unauthorized maneuver. Consider this a data gap."
    )
