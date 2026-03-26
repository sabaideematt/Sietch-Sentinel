# ingestion/

**Layer 1: Data Ingestion & Orbital Mechanics**

Fetches Two-Line Element sets from Space-Track.org and CelesTrak, propagates them to position/velocity state vectors via SGP4/SDP4, and estimates delta-V between consecutive TLE pairs to identify maneuver candidates.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `TLEFetcher`, `OrbitalPropagator`, `DeltaVCalculator` |
| `tle_fetcher.py` | `TLEFetcher` — authenticated fetcher for Space-Track.org (historical + latest TLEs) with CelesTrak fallback. Returns `TLERecord` models. |
| `propagator.py` | `OrbitalPropagator` — wraps `sgp4` to propagate a TLE to a `StateVector` (position_km, velocity_km_s) at any epoch. Supports single-point and time-series propagation. |
| `delta_v.py` | `DeltaVCalculator` — estimates delta-V (m/s) from consecutive TLE pairs by comparing propagated velocity vectors. Computes uncertainty bounds and confidence intervals. Flags maneuver candidates above configurable thresholds. |

## Data Flow

```
Space-Track / CelesTrak
        │
        ▼
   TLEFetcher  →  TLERecord[]
        │
        ▼
 OrbitalPropagator  →  StateVector[]
        │
        ▼
 DeltaVCalculator  →  DeltaVEstimate[]
        │
        ▼
   Layer 2 (Triage)
```
