"""Tool 3: Delta-V Calculator — Hohmann transfer estimation, maneuver characterization."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class DeltaVCalculatorInput(BaseModel):
    norad_cat_id: int = Field(description="NORAD catalog ID")
    days_back: int = Field(default=30, description="Days of TLE history to analyze")


@tool("delta_v_calculator", args_schema=DeltaVCalculatorInput)
def delta_v_calculator_tool(norad_cat_id: int, days_back: int = 30) -> str:
    """Calculate delta-V estimates from TLE history to identify maneuver candidates."""
    import asyncio
    from datetime import datetime, timedelta

    from src.ingestion.tle_fetcher import TLEFetcher
    from src.ingestion.delta_v import DeltaVCalculator

    fetcher = TLEFetcher()
    calculator = DeltaVCalculator()
    start = datetime.utcnow() - timedelta(days=days_back)

    loop = asyncio.new_event_loop()
    try:
        tles = loop.run_until_complete(fetcher.fetch_tle_history(norad_cat_id, start))
    finally:
        loop.close()

    if len(tles) < 2:
        return f"Insufficient TLE data for NORAD {norad_cat_id} (need ≥2 TLEs, got {len(tles)})."

    estimates = calculator.estimate_series(tles)
    if not estimates:
        return "No delta-V estimates could be computed from the TLE series."

    lines = [f"Delta-V estimates for NORAD {norad_cat_id} ({len(estimates)} pairs):"]
    for est in estimates:
        lines.append(
            f"  {est.epoch_before.isoformat()} → {est.epoch_after.isoformat()}: "
            f"Δv={est.delta_v_m_s:.2f} m/s ± {est.uncertainty_m_s:.2f} m/s "
            f"(CI: [{est.confidence_interval[0]:.2f}, {est.confidence_interval[1]:.2f}])"
        )
    return "\n".join(lines)
