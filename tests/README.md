# tests/

**Pytest test suite covering all 6 architectural layers.**

Run with: `pytest` or `pytest --cov=src` for coverage.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Test package marker |
| `conftest.py` | Shared fixtures: `tmp_db` (temp SQLite path), `sample_tle_record`, `sample_tle_pair`, `sample_delta_v`, `sample_anomaly_score`, `sample_investigation_result` (complete with TTP matches and delta-V), `memory_store` (isolated MemoryStore with temp DB). Sets test environment variables to avoid touching production data. |
| `test_ingestion.py` | **Layer 1** — SGP4 propagation (position/velocity magnitude checks for LEO), time-series propagation, delta-V estimation from TLE pairs, edge cases (single TLE, insufficient data). |
| `test_triage.py` | **Layer 2** — Isolation Forest fit/score, anomalous data scores higher than normal, severity routing (LOW/MID/HIGH), `should_investigate` gating, uncertainty weighting (high uncertainty dampens score). |
| `test_agent_tools.py` | **Layer 3** — TTP matcher (SPARTA + ATT&CK matching, indicator scores, counterfactual gating for HIGH confidence), operator schedule (no-schedule data gap), fleet correlator (empty fleet). |
| `test_memory.py` | **Layer 4** — SQLite CRUD (profile upsert/get, investigation logging, threshold updates, feedback roundtrip), sync log (pending/synced lifecycle), MemoryStore write-through (profile and investigation), reconciliation with empty sync log. |
| `test_reports.py` | **Layer 5** — JSON report validity and required fields, delta-V uncertainty range in output, TTP confidence tiers and indicator scores, NL brief sections, insufficient data flag, file save, STIX 2.1 bundle structure and serialization. |
| `test_schemas.py` | **Schemas** — Enum values, TLE serialization roundtrip, DeltaVEstimate confidence interval ordering and `delta_v_uncertainty_range` auto-population, InvestigationResult field completeness, TTP match confidence tiers with `indicator_score`, `investigation_budget_used` block, SpaceWeatherContext, SatelliteProfile defaults. |
| `test_feedback.py` | **Layer 6** — Feedback submission (confirmed, false positive, needs correction), confidence override recording, feedback stats defaults. |
