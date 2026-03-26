# src/

Root package for Sietch Sentinel. Contains shared modules and all six architectural layers as subpackages.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package root; defines `__version__` |
| `config.py` | Central configuration via Pydantic-Settings, loads from `.env`. Manages paths (`DATA_DIR`, `MODELS_DIR`, `CHROMA_PERSIST_DIR`), API credentials, and agent budget defaults. |
| `schemas.py` | Shared Pydantic models used across all layers: `TLERecord`, `StateVector`, `DeltaVEstimate`, `SpaceWeatherContext`, `AnomalyScore`, `InvestigationRequest`, `InvestigationResult`, `TTPMatch`, `ResourceUsage`, `SatelliteProfile`, `AnalystFeedback`, and supporting enums (`OrbitRegime`, `AnomalySeverity`, `ConfidenceTier`, `FeedbackVerdict`). |
| `cli.py` | Click-based CLI entry point. Commands: `ingest` (TLE fetch + delta-V), `investigate` (run agent loop), `profile` (view satellite profile), `check-config` (verify environment). |

## Subpackages

| Directory | Layer | Description |
|---|---|---|
| `ingestion/` | Layer 1 | TLE fetching, SGP4 orbital propagation, delta-V estimation |
| `triage/` | Layer 2 | ML anomaly detection (Isolation Forest, LSTM Autoencoder) and severity routing |
| `agent/` | Layer 3 | Claude ReAct orchestrator with 11 investigation tools |
| `memory/` | Layer 4 | Three-backend memory store (SQLite, Redis, ChromaDB) with write-through consistency |
| `reports/` | Layer 5 | Report generation (JSON, Markdown, STIX 2.1) and SOC export (Splunk HEC, Elastic ECS) |
| `feedback/` | Layer 6 | Analyst feedback processing, threshold tuning, retraining triggers |
