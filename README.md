# Sietch Sentinel

**Agentic AI system for autonomous satellite constellation cyber-anomaly detection.**

Sietch Sentinel monitors orbital behavior across satellite constellations, detects anomalies that may indicate cyber compromise, investigates them using multi-source evidence, maps findings to the [SPARTA](https://sparta.aerospace.org) and [MITRE ATT&CK](https://attack.mitre.org) cybersecurity frameworks, and produces analyst-ready threat briefs compatible with standard SOC tooling.

---

## Architecture (6 Layers)

| Layer | Purpose | Key Components |
|---|---|---|
| **1. Ingestion** | TLE fetch, SGP4 propagation, delta-V estimation | Space-Track.org, CelesTrak, sgp4 |
| **2. Triage ML** | Anomaly detection & severity routing | Isolation Forest, LSTM Autoencoder |
| **3. Orchestrator Agent** | Claude ReAct investigation loop (11 tools) | Anthropic SDK, LangChain |
| **4. Memory Layer** | Persistent per-satellite knowledge base | SQLite, ChromaDB, Redis |
| **5. Reports & SOC** | Multi-format output & SIEM integration | STIX 2.1, Splunk HEC, Elastic ECS |
| **6. Feedback Loop** | Analyst review → retraining pipeline | Verdict processing, threshold tuning |

## Project Structure

```
Sietch-Sentinel/
├── src/
│   ├── __init__.py          # Package root
│   ├── config.py            # Central config (from .env)
│   ├── schemas.py           # Shared Pydantic models
│   ├── cli.py               # CLI entry point
│   ├── ingestion/           # Layer 1: TLE fetch, propagation, delta-V
│   │   ├── tle_fetcher.py
│   │   ├── propagator.py
│   │   └── delta_v.py
│   ├── triage/              # Layer 2: ML anomaly detection
│   │   ├── isolation_forest.py
│   │   ├── lstm_autoencoder.py
│   │   └── scorer.py
│   ├── agent/               # Layer 3: Claude orchestrator
│   │   ├── orchestrator.py
│   │   └── tools/           # 11 agent tools
│   │       ├── tle_fetcher.py
│   │       ├── orbital_propagator.py
│   │       ├── delta_v_calculator.py
│   │       ├── space_weather.py
│   │       ├── conjunction_data.py
│   │       ├── ground_station.py
│   │       ├── ttp_matcher.py
│   │       ├── operator_schedule.py
│   │       ├── fleet_correlator.py
│   │       ├── memory_rw.py
│   │       └── analyst_feedback.py
│   ├── memory/              # Layer 4: SQLite + ChromaDB + Redis
│   │   └── store.py
│   ├── reports/             # Layer 5: Reports & SOC export
│   │   ├── generator.py
│   │   ├── stix_builder.py
│   │   └── soc_export.py
│   └── feedback/            # Layer 6: Analyst feedback loop
│       └── handler.py
├── .env.example             # Environment variable template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/sabaideematt/Sietch-Sentinel.git
cd Sietch-Sentinel
cp .env.example .env
# Edit .env with your credentials
```

### 2. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 3. Verify Configuration

```bash
python -m src.cli check-config
```

### 4. Ingest TLE Data

```bash
# Fetch TLEs and compute delta-V for a GEO satellite (e.g., NORAD 36411)
python -m src.cli ingest 36411 --days 30
```

### 5. Run an Investigation

```bash
# Investigate an anomaly (requires ANTHROPIC_API_KEY)
python -m src.cli investigate 36411 --severity mid
```

### 6. Docker

```bash
docker-compose up --build
```

## External Data Sources

| Source | Data | Access |
|---|---|---|
| [Space-Track.org](https://www.space-track.org) | TLE catalog, CDMs | Free account |
| [CelesTrak](https://celestrak.org) | TLE mirror | Free / open |
| [NOAA SWPC](https://www.swpc.noaa.gov) | Space weather (Kp, solar flux, CME) | Free / open |
| [SatNOGS](https://network.satnogs.org) | Ground station observations | Free / open |
| [SPARTA](https://sparta.aerospace.org) | Space TTP matrix | Free / open |
| [MITRE ATT&CK](https://attack.mitre.org) | Cyber TTP knowledge base | Free / open |

## Required API Keys

- **Space-Track.org** — Free account at [space-track.org](https://www.space-track.org/auth/createAccount)
- **Anthropic** — API key for Claude (orchestrator agent)

## License

TBD
