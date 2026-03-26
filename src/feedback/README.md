# feedback/

**Layer 6: Analyst Feedback Loop**

Processes analyst reviews of investigation results, updates satellite profiles, tunes anomaly thresholds, and triggers ML retraining when sufficient labeled data accumulates.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `FeedbackHandler` |
| `handler.py` | `FeedbackHandler` — processes `AnalystFeedback` submissions. Persists feedback to the Memory Layer, updates satellite profile counters (total investigations, false positive count), applies confidence overrides, adjusts per-satellite anomaly thresholds on false positive verdicts, and checks whether accumulated labeled feedback (per orbit regime) has crossed the retraining threshold to trigger ML model updates. |

## Feedback Verdicts

| Verdict | Effect |
|---|---|
| `confirmed` | Validates investigation result, increments true positive count |
| `false_positive` | Increments FP count, relaxes anomaly thresholds for the satellite |
| `needs_correction` | Records analyst's corrected assessment for retraining |
| `escalate` | Flags for senior analyst review |

## Retraining Trigger

When the total number of labeled feedback entries for a given orbit regime exceeds a configurable threshold (default: 50), the handler signals that the triage ML models for that regime are eligible for retraining with the new labels.
