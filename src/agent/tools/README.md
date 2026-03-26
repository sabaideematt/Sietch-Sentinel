# agent/tools/

**11 Investigation Tools for the Orchestrator Agent**

Each tool is a LangChain `@tool`-decorated function with a Pydantic input schema. The orchestrator selects and invokes tools during the ReAct loop.

## Files

| File | Tool # | Purpose |
|---|---|---|
| `__init__.py` | — | Exports the `TOOL_LIST` containing all 11 tools |
| `tle_fetcher.py` | 1 | **TLE Fetcher** — fetch latest or historical TLEs for a NORAD ID. Wraps `ingestion.TLEFetcher`. |
| `orbital_propagator.py` | 2 | **Orbital Propagator** — propagate a TLE to position/velocity at a given epoch. Wraps `ingestion.OrbitalPropagator`. |
| `delta_v_calculator.py` | 3 | **Delta-V Calculator** — estimate delta-V from TLE history with uncertainty bounds. Wraps `ingestion.DeltaVCalculator`. |
| `space_weather.py` | 4 | **Space Weather Checker** — query NOAA SWPC for Kp index, solar flux, and CME events. Used to rule out natural causes for orbital anomalies. |
| `conjunction_data.py` | 5 | **Conjunction Data** — query Space-Track CDMs for proximity events. Distinguishes evasive maneuvers from suspicious ones. |
| `ground_station.py` | 6 | **Ground Station Correlator** — query SatNOGS for observation data. Identifies coverage gaps and anomalous signal timing. |
| `ttp_matcher.py` | 7 | **SPARTA + ATT&CK Matcher** — dual-framework TTP matching with confidence tiers (HIGH/MED/LOW) and indicator scores. HIGH confidence requires natural causes to be ruled out first. |
| `operator_schedule.py` | 8 | **Operator Schedule Check** — check for published operator maneuver schedules. Placeholder — flags data gap when no schedule is available. |
| `fleet_correlator.py` | 9 | **Fleet Correlator** — check for simultaneous anomalies across a satellite fleet by operator/orbit regime. Placeholder. |
| `memory_rw.py` | 10 | **Memory Read/Write** — read satellite profiles and past investigation summaries from the Memory Layer; write new profiles and investigation results. |
| `analyst_feedback.py` | 11 | **Analyst Feedback Reader** — read past analyst feedback for a satellite or investigation from the Memory Layer. |

## Counterfactual Requirement

The TTP matcher (Tool 7) enforces the architecture's counterfactual rule: no TTP match can reach HIGH confidence unless natural causes have been explicitly ruled out via space weather, conjunction data, or operator schedule checks.
