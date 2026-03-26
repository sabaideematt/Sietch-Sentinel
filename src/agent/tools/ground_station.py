"""Tool 6: Ground Station Correlator — SatNOGS observation DB, pass timing, coverage gaps."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GroundStationInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID")
    days_back: int = Field(default=7, description="Days of observation history to check")


@tool("ground_station_correlator", args_schema=GroundStationInput)
def ground_station_tool(norad_cat_id: int, days_back: int = 7) -> str:
    """Query SatNOGS for ground station observations of the target satellite.
    Identifies coverage gaps and anomalous signal timing."""
    import httpx
    from datetime import datetime, timedelta

    start = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")

    try:
        resp = httpx.get(
            "https://network.satnogs.org/api/observations/",
            params={
                "satellite__norad_cat_id": norad_cat_id,
                "start": start,
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        observations = resp.json()

        if not observations:
            return f"No SatNOGS observations found for NORAD {norad_cat_id} in the last {days_back} days."

        lines = [f"SatNOGS observations for NORAD {norad_cat_id}: {len(observations)} total"]
        for obs in observations[:5]:
            lines.append(
                f"  ID: {obs.get('id')} | "
                f"Start: {obs.get('start', 'N/A')} | "
                f"End: {obs.get('end', 'N/A')} | "
                f"Status: {obs.get('vetted_status', 'N/A')} | "
                f"Station: {obs.get('ground_station', 'N/A')}"
            )

        # Identify coverage gaps > 24 hours
        if len(observations) >= 2:
            sorted_obs = sorted(observations, key=lambda o: o.get("start", ""))
            gaps = []
            for i in range(len(sorted_obs) - 1):
                try:
                    end_time = datetime.fromisoformat(sorted_obs[i]["end"].replace("Z", "+00:00"))
                    next_start = datetime.fromisoformat(sorted_obs[i + 1]["start"].replace("Z", "+00:00"))
                    gap = (next_start - end_time).total_seconds() / 3600
                    if gap > 24:
                        gaps.append(f"    {end_time.isoformat()} → {next_start.isoformat()} ({gap:.1f} hrs)")
                except (KeyError, ValueError):
                    continue
            if gaps:
                lines.append(f"  Coverage gaps > 24h: {len(gaps)}")
                lines.extend(gaps[:3])

        return "\n".join(lines)

    except Exception as e:
        return f"SatNOGS query failed: {e}"
