"""SGP4/SDP4 orbital propagation — TLE → state vectors."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sgp4.api import Satrec, WGS72
from sgp4.api import jday

from src.schemas import TLERecord, StateVector

logger = logging.getLogger(__name__)


class OrbitalPropagator:
    """Propagate TLEs to position + velocity state vectors using SGP4."""

    @staticmethod
    def propagate_at_epoch(tle: TLERecord, dt: Optional[datetime] = None) -> Optional[StateVector]:
        """Propagate a TLE to a given datetime (defaults to TLE epoch)."""
        try:
            sat = Satrec.twoline2rv(tle.line1, tle.line2, WGS72)
            dt = dt or tle.epoch
            jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
            e, r, v = sat.sgp4(jd, fr)
            if e != 0:
                logger.warning("SGP4 error code %d for NORAD %d", e, tle.norad_cat_id)
                return None
            return StateVector(
                norad_cat_id=tle.norad_cat_id,
                epoch=dt,
                position_km=(r[0], r[1], r[2]),
                velocity_km_s=(v[0], v[1], v[2]),
            )
        except Exception as exc:
            logger.error("Propagation failed for NORAD %d: %s", tle.norad_cat_id, exc)
            return None

    @staticmethod
    def propagate_series(
        tle: TLERecord,
        start: datetime,
        end: datetime,
        step_minutes: float = 10.0,
    ) -> list[StateVector]:
        """Propagate a TLE across a time range, returning a series of state vectors."""
        vectors: list[StateVector] = []
        sat = Satrec.twoline2rv(tle.line1, tle.line2, WGS72)
        current = start
        step = timedelta(minutes=step_minutes)
        while current <= end:
            jd, fr = jday(
                current.year, current.month, current.day,
                current.hour, current.minute,
                current.second + current.microsecond / 1e6,
            )
            e, r, v = sat.sgp4(jd, fr)
            if e == 0:
                vectors.append(StateVector(
                    norad_cat_id=tle.norad_cat_id,
                    epoch=current,
                    position_km=(r[0], r[1], r[2]),
                    velocity_km_s=(v[0], v[1], v[2]),
                ))
            current += step
        return vectors
