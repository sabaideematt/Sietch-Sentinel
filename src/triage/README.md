# triage/

**Layer 2: Triage ML — Anomaly Detection & Severity Routing**

Two complementary ML models score orbital anomalies, and a composite scorer routes them to severity tiers for investigation.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `IsolationForestDetector`, `LSTMAutoencoder`, `TriageScorer` |
| `isolation_forest.py` | `IsolationForestDetector` — point anomaly detection using scikit-learn's Isolation Forest. Trains per orbit regime (GEO/MEO/LEO/HEO). Features: delta-V, uncertainty, semi-major axis, eccentricity, inclination. Supports save/load for model persistence. |
| `lstm_autoencoder.py` | `LSTMAutoencoder` — sequence anomaly detection using a Keras LSTM autoencoder. Trains on 30-day sliding windows of orbital element time series. Anomaly score = reconstruction error. Supports save/load. |
| `scorer.py` | `TriageScorer` — combines Isolation Forest and LSTM scores with configurable weights, applies uncertainty dampening when delta-V uncertainty is high, and routes to severity tiers: **LOW** (log only), **MID** (investigate), **HIGH** (investigate + priority). Per-satellite adaptive thresholds override defaults when available. |

## Severity Routing

| Composite Score | Severity | Action |
|---|---|---|
| < 0.4 | LOW | Log, no investigation |
| 0.4 – 0.7 | MID | Queue for agent investigation |
| > 0.7 | HIGH | Priority investigation |
