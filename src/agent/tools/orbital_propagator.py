"""Tool 2: Orbital Propagator — SGP4/SDP4, position + velocity state vector diffs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class OrbitalPropagatorInput(BaseModel):
    tle_line1: str = Field(description="TLE line 1")
    tle_line2: str = Field(description="TLE line 2")
    norad_cat_id: int = Field(description="NORAD catalog ID")
    propagate_to: Optional[str] = Field(
        default=None,
        description="ISO-format datetime to propagate to (defaults to TLE epoch)",
    )


@tool("orbital_propagator", args_schema=OrbitalPropagatorInput)
def orbital_propagator_tool(
    tle_line1: str,
    tle_line2: str,
    norad_cat_id: int,
    propagate_to: Optional[str] = None,
) -> str:
    """Propagate a TLE to a specific time using SGP4. Returns position and velocity vectors."""
    from src.ingestion.propagator import OrbitalPropagator
    from src.schemas import TLERecord

    tle = TLERecord(
        norad_cat_id=norad_cat_id,
        object_name=f"NORAD-{norad_cat_id}",
        epoch=datetime.utcnow(),
        line1=tle_line1,
        line2=tle_line2,
    )

    dt = datetime.fromisoformat(propagate_to) if propagate_to else None
    sv = OrbitalPropagator.propagate_at_epoch(tle, dt)

    if sv is None:
        return f"Propagation failed for NORAD {norad_cat_id}."

    return (
        f"State vector at {sv.epoch.isoformat()}:\n"
        f"  Position (km): x={sv.position_km[0]:.3f}, y={sv.position_km[1]:.3f}, z={sv.position_km[2]:.3f}\n"
        f"  Velocity (km/s): vx={sv.velocity_km_s[0]:.6f}, vy={sv.velocity_km_s[1]:.6f}, vz={sv.velocity_km_s[2]:.6f}"
    )
