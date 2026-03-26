"""Tool 1: TLE Fetcher — Space-Track.org API, historical + live TLEs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class TLEFetcherInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID of the satellite")
    days_back: int = Field(default=30, description="Number of days of history to fetch")


@tool("tle_fetcher", args_schema=TLEFetcherInput)
def tle_fetcher_tool(norad_cat_id: int, days_back: int = 30) -> str:
    """Fetch TLE data from Space-Track.org for a satellite. Returns latest and historical TLEs."""
    from src.ingestion.tle_fetcher import TLEFetcher

    fetcher = TLEFetcher()
    start = datetime.utcnow() - timedelta(days=days_back)

    # Run async fetch in sync context
    loop = asyncio.new_event_loop()
    try:
        latest = loop.run_until_complete(fetcher.fetch_latest_tle(norad_cat_id))
        history = loop.run_until_complete(fetcher.fetch_tle_history(norad_cat_id, start))
    finally:
        loop.close()

    if latest is None and not history:
        return f"No TLE data found for NORAD {norad_cat_id}."

    parts = []
    if latest:
        parts.append(f"Latest TLE (source: {latest.source}):\n  L1: {latest.line1}\n  L2: {latest.line2}")
    parts.append(f"Historical TLEs fetched: {len(history)} records over {days_back} days")
    return "\n".join(parts)
