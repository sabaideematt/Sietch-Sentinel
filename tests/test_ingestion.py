"""Tests for Layer 1: Ingestion — propagation and delta-V estimation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest


class TestOrbitalPropagator:
    """SGP4 propagation tests."""

    def test_propagate_at_epoch_returns_state_vector(self, sample_tle_record):
        from src.ingestion.propagator import OrbitalPropagator

        sv = OrbitalPropagator.propagate_at_epoch(sample_tle_record)
        assert sv is not None
        assert sv.norad_cat_id == 25544
        # ISS should be in LEO — position magnitude ~6500-6900 km
        r_mag = math.sqrt(sum(x**2 for x in sv.position_km))
        assert 6000 < r_mag < 7000, f"Position magnitude {r_mag} km outside LEO range"
        # Velocity ~7.5-7.8 km/s for LEO
        v_mag = math.sqrt(sum(x**2 for x in sv.velocity_km_s))
        assert 7.0 < v_mag < 8.0, f"Velocity magnitude {v_mag} km/s outside LEO range"

    def test_propagate_at_future_time(self, sample_tle_record):
        from src.ingestion.propagator import OrbitalPropagator

        future = sample_tle_record.epoch + timedelta(hours=1)
        sv = OrbitalPropagator.propagate_at_epoch(sample_tle_record, future)
        assert sv is not None
        assert sv.epoch == future

    def test_propagate_series(self, sample_tle_record):
        from src.ingestion.propagator import OrbitalPropagator

        start = sample_tle_record.epoch
        end = start + timedelta(hours=2)
        series = OrbitalPropagator.propagate_series(
            sample_tle_record, start, end, step_minutes=30
        )
        # 2 hours at 30-min steps = 5 points (0, 30, 60, 90, 120 min)
        assert len(series) == 5
        assert all(sv.norad_cat_id == 25544 for sv in series)


class TestDeltaVCalculator:
    """Delta-V estimation tests."""

    def test_estimate_from_tle_pair(self, sample_tle_pair):
        from src.ingestion.delta_v import DeltaVCalculator

        tle1, tle2 = sample_tle_pair
        calc = DeltaVCalculator()
        est = calc.estimate_from_tle_pair(tle1, tle2)
        # Same TLE data → should produce near-zero delta-V
        assert est is not None
        assert est.norad_cat_id == 25544
        assert est.delta_v_m_s >= 0
        assert est.uncertainty_m_s >= 0
        assert est.confidence_interval[0] <= est.confidence_interval[1]

    def test_estimate_series(self, sample_tle_pair):
        from src.ingestion.delta_v import DeltaVCalculator

        calc = DeltaVCalculator()
        estimates = calc.estimate_series(list(sample_tle_pair))
        assert len(estimates) == 1

    def test_estimate_series_insufficient_data(self, sample_tle_record):
        from src.ingestion.delta_v import DeltaVCalculator

        calc = DeltaVCalculator()
        # Single TLE → no pairs → no estimates
        estimates = calc.estimate_series([sample_tle_record])
        assert len(estimates) == 0
