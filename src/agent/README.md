# agent/

**Layer 3: Orchestrator Agent — Claude ReAct Investigation Loop**

A Claude-powered ReAct agent that investigates mid/high-severity anomalies using 11 tools, operating under strict budget constraints.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `Orchestrator` |
| `orchestrator.py` | `Orchestrator` — drives the Claude ReAct loop. Receives an `InvestigationRequest`, builds the system prompt with satellite context and available tools, then iterates Thought → Action → Observation until a conclusion is reached or budget is exhausted. Enforces max 15 tool calls, 8K tokens, and 90s wall-clock timeout. Produces an `InvestigationResult` with evidence chain, TTP matches, and executive summary. |

## Subdirectory

| Directory | Description |
|---|---|
| `tools/` | 11 LangChain-compatible tools available to the orchestrator agent |

## Budget Constraints

| Limit | Default |
|---|---|
| Max tool calls | 15 |
| Max tokens | 8,000 |
| Wall-clock timeout | 90 seconds |

The agent degrades gracefully when budget is exhausted — it emits a partial result with `insufficient_data=True` and `budget_exhausted=True`.
