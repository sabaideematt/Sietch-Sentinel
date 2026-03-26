"""Delta-V estimation from consecutive TLE pairs."""

from __future__ import annotations

import logging
import math
from typing import Optional

from src.schemas import TLERecord, StateVector, DeltaVEstimate
from src.ingestion.propagator import OrbitalPropagator

logger = logging.getLogger(__name__)


class DeltaVCalculator:
    """Derive maneuver candidates from consecutive TLE-derived state vectors."""

    def __init__(self, propagator: Optional[OrbitalPropagator] = None):
        self.propagator = propagator or OrbitalPropagator()

    def estimate_from_tle_pair(
        self, tle_before: TLERecord, tle_after: TLERecord
    ) -> Optional[DeltaVEstimate]:
        """
        Estimate delta-V by propagating tle_before forward to tle_after's epoch,
        then computing the velocity difference.
        """
        # Propagate tle_before to tle_after's epoch
        sv_predicted = self.propagator.propagate_at_epoch(tle_before, tle_after.epoch)
        sv_actual = self.propagator.propagate_at_epoch(tle_after)

        if sv_predicted is None or sv_actual is None:
            return None

        dv = self._velocity_diff_magnitude(sv_predicted, sv_actual)
        uncertainty = self._estimate_uncertainty(tle_before, tle_after, dv)

        return DeltaVEstimate(
            norad_cat_id=tle_before.norad_cat_id,
            epoch_before=tle_before.epoch,
            epoch_after=tle_after.epoch,
            delta_v_m_s=dv * 1000.0,  # km/s → m/s
            uncertainty_m_s=uncertainty * 1000.0,
            confidence_interval=(
                max(0.0, (dv - uncertainty) * 1000.0),
                (dv + uncertainty) * 1000.0,
            ),
        )

    def estimate_series(self, tles: list[TLERecord]) -> list[DeltaVEstimate]:
        """Process a chronological TLE series into delta-V estimates."""
        estimates: list[DeltaVEstimate] = []
        for i in range(len(tles) - 1):
            est = self.estimate_from_tle_pair(tles[i], tles[i + 1])
            if est is not None:
                estimates.append(est)
        return estimates

    # ── Helpers ──

    @staticmethod
    def _velocity_diff_magnitude(sv1: StateVector, sv2: StateVector) -> float:
        """Compute |Δv| in km/s between two state vectors."""
        dx = sv2.velocity_km_s[0] - sv1.velocity_km_s[0]
        dy = sv2.velocity_km_s[1] - sv1.velocity_km_s[1]
        dz = sv2.velocity_km_s[2] - sv1.velocity_km_s[2]
        return math.sqrt(dx**2 + dy**2 + dz**2)

    @staticmethod
    def _estimate_uncertainty(
        tle_before: TLERecord, tle_after: TLERecord, dv_km_s: float
    ) -> float:
        """
        Heuristic uncertainty based on TLE age gap and delta-V magnitude.
        Proper implementation would use covariance / fit residuals.
        """
        # Placeholder: 10% of delta-V + baseline noise floor of 0.001 km/s
        return dv_km_s * 0.10 + 0.001
