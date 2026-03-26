"""Tool 4: Space Weather Checker — NOAA SWPC API (Kp index, solar flux, CME correlation)."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class SpaceWeatherInput(BaseModel):
    date: str = Field(
        default="",
        description="ISO date (YYYY-MM-DD) to check. Defaults to today.",
    )


@tool("space_weather_checker", args_schema=SpaceWeatherInput)
def space_weather_tool(date: str = "") -> str:
    """Check space weather conditions (Kp index, solar flux, CME events) from NOAA SWPC.
    Used to rule out natural causes for orbital anomalies."""
    import httpx
    from datetime import datetime, timedelta

    target = datetime.fromisoformat(date) if date else datetime.utcnow()
    results = []

    # Kp index (planetary geomagnetic index)
    try:
        resp = httpx.get(
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
            timeout=10,
        )
        resp.raise_for_status()
        kp_data = resp.json()
        # Last few entries
        recent = kp_data[-5:] if len(kp_data) > 5 else kp_data
        results.append("Recent Kp indices:")
        for entry in recent:
            results.append(f"  {entry[0]}: Kp={entry[1]}")
    except Exception as e:
        results.append(f"Kp index fetch failed: {e}")

    # Solar flux (F10.7)
    try:
        resp = httpx.get(
            "https://services.swpc.noaa.gov/json/f107_cm_flux.json",
            timeout=10,
        )
        resp.raise_for_status()
        flux_data = resp.json()
        if flux_data:
            latest = flux_data[-1]
            results.append(f"Solar flux (F10.7): {latest.get('flux', 'N/A')} SFU at {latest.get('time_tag', 'N/A')}")
    except Exception as e:
        results.append(f"Solar flux fetch failed: {e}")

    # CME events
    try:
        start_str = (target - timedelta(days=3)).strftime("%Y-%m-%d")
        end_str = target.strftime("%Y-%m-%d")
        resp = httpx.get(
            f"https://api.nasa.gov/DONKI/CME?startDate={start_str}&endDate={end_str}&api_key=DEMO_KEY",
            timeout=10,
        )
        resp.raise_for_status()
        cmes = resp.json()
        results.append(f"CME events in ±3 day window: {len(cmes)}")
        for cme in cmes[:3]:
            results.append(f"  {cme.get('activityID', 'N/A')}: {cme.get('startTime', 'N/A')}")
    except Exception as e:
        results.append(f"CME data fetch failed: {e}")

    return "\n".join(results) if results else "No space weather data retrieved."
