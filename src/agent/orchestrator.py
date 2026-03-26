"""Layer 3: Orchestrator Agent — Claude ReAct loop with resource budgets."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

from src.config import settings
from src.schemas import (
    AnomalyScore,
    InvestigationRequest,
    InvestigationResult,
    OrbitRegime,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Sietch Sentinel, an autonomous satellite cyber-anomaly investigator.

Your mission: Investigate orbital anomalies to determine whether they indicate cyber compromise of a space vehicle, or can be explained by natural/operational causes.

## Your Investigation Framework
1. OBSERVE — Gather data about the anomaly (TLEs, delta-V, space weather, conjunctions)
2. REASON — Analyze evidence, compare against satellite baseline from memory
3. ACT — Call tools to gather additional evidence or rule out natural causes
4. DECIDE — Map findings to SPARTA + MITRE ATT&CK TTPs, or conclude natural cause

## Critical Rules
- You MUST rule out natural causes (space weather, conjunction avoidance, scheduled stationkeeping) BEFORE assigning any TTP match with HIGH confidence
- Attribution is HUMAN-ONLY — never attribute an anomaly to a specific threat actor
- If evidence is insufficient, produce a partial report with INSUFFICIENT DATA flag
- Always check the satellite's baseline profile from memory before concluding
- Consider operator schedules and fleet-wide patterns

## Available Frameworks
- SPARTA (Space Attack Research & Tactic Analysis) — space-specific TTPs
- MITRE ATT&CK — mapped to space context for cyber TTPs

## Resource Budget
- Maximum {max_tool_calls} tool calls
- Maximum {max_tokens} tokens of accumulated results
- Maximum {timeout}s wall-clock time
- If budget exhausted, produce partial report with what you have

Investigate thoroughly but efficiently. Prioritize the most informative tools first.
"""


class Orchestrator:
    """Claude-powered ReAct agent with budget-constrained investigation loop."""

    def __init__(self):
        self.max_tool_calls = settings.agent_max_tool_calls
        self.max_tokens = settings.agent_max_tokens
        self.timeout_seconds = settings.agent_timeout_seconds

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        """Run a full investigation for a triaged anomaly."""
        start_time = time.time()
        logger.info(
            "Starting investigation %s for NORAD %d (severity: %s)",
            request.investigation_id,
            request.anomaly.norad_cat_id,
            request.anomaly.severity.value,
        )

        try:
            result = await self._run_agent(request, start_time)
        except Exception as exc:
            logger.error("Investigation %s failed: %s", request.investigation_id, exc)
            result = self._build_partial_result(request, start_time, error=str(exc))

        elapsed = time.time() - start_time
        result.wall_clock_seconds = elapsed
        logger.info(
            "Investigation %s completed in %.1fs (%d tool calls)",
            request.investigation_id,
            elapsed,
            result.tool_calls_used,
        )
        return result

    async def _run_agent(
        self, request: InvestigationRequest, start_time: float
    ) -> InvestigationResult:
        """Execute the ReAct agent loop using LangGraph."""
        from anthropic import Anthropic
        from src.agent.tools import ALL_TOOLS

        client = Anthropic(api_key=settings.anthropic_api_key)

        if not settings.anthropic_api_key:
            logger.warning("No Anthropic API key configured — returning stub result.")
            return self._build_partial_result(
                request, start_time, error="ANTHROPIC_API_KEY not configured"
            )

        system = SYSTEM_PROMPT.format(
            max_tool_calls=self.max_tool_calls,
            max_tokens=self.max_tokens,
            timeout=self.timeout_seconds,
        )

        # Build initial user message with investigation context
        user_msg = (
            f"Investigate the following orbital anomaly:\n\n"
            f"NORAD Cat ID: {request.anomaly.norad_cat_id}\n"
            f"Satellite: {request.satellite_name or 'Unknown'}\n"
            f"Orbit Regime: {request.orbit_regime.value}\n"
            f"Anomaly Score: {request.anomaly.composite_score:.4f}\n"
            f"Severity: {request.anomaly.severity.value}\n"
            f"IF Score: {request.anomaly.isolation_forest_score:.4f}\n"
            f"LSTM Score: {request.anomaly.lstm_reconstruction_error:.4f}\n"
        )

        if request.anomaly.delta_v:
            dv = request.anomaly.delta_v
            user_msg += (
                f"\nDelta-V: {dv.delta_v_m_s:.2f} m/s ± {dv.uncertainty_m_s:.2f} m/s\n"
                f"Confidence Interval: [{dv.confidence_interval[0]:.2f}, {dv.confidence_interval[1]:.2f}]\n"
            )

        user_msg += (
            f"\nTimestamp: {request.anomaly.timestamp.isoformat()}\n"
            f"\nBegin your investigation. Use tools to gather evidence, rule out "
            f"natural causes, and determine if this anomaly warrants a TTP match."
        )

        # Build tool definitions for Claude
        tool_definitions = []
        for t in ALL_TOOLS:
            schema = t.args_schema.model_json_schema() if t.args_schema else {}
            tool_definitions.append({
                "name": t.name,
                "description": t.description,
                "input_schema": schema,
            })

        messages = [{"role": "user", "content": user_msg}]
        tool_calls_used = 0
        tokens_used = 0
        evidence_chain = []

        # ReAct loop
        while tool_calls_used < self.max_tool_calls:
            elapsed = time.time() - start_time
            if elapsed > self.timeout_seconds:
                logger.warning("Investigation timeout reached at %.1fs", elapsed)
                break

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system,
                tools=tool_definitions,
                messages=messages,
            )

            tokens_used += response.usage.input_tokens + response.usage.output_tokens

            # Process response blocks
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn":
                # Agent is done — extract final text
                for block in assistant_content:
                    if hasattr(block, "text"):
                        evidence_chain.append(block.text)
                break

            # Process tool use blocks
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_calls_used += 1
                    tool_name = block.name
                    tool_input = block.input

                    # Find and execute the tool
                    tool_output = self._execute_tool(tool_name, tool_input, ALL_TOOLS)
                    evidence_chain.append(f"[{tool_name}] {tool_output[:500]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_output,
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        # Extract executive summary from the last text response
        executive_summary = ""
        for block in messages[-1].get("content", []) if isinstance(messages[-1], dict) else []:
            if isinstance(block, dict) and block.get("type") == "text":
                executive_summary = block["text"]
            elif hasattr(block, "text"):
                executive_summary = block.text

        return InvestigationResult(
            investigation_id=request.investigation_id,
            norad_cat_id=request.anomaly.norad_cat_id,
            satellite_name=request.satellite_name,
            orbit_regime=request.orbit_regime,
            anomaly_score=request.anomaly.composite_score,
            delta_v=request.anomaly.delta_v,
            evidence_chain=evidence_chain,
            tool_calls_used=tool_calls_used,
            tokens_used=tokens_used,
            executive_summary=executive_summary or "Investigation completed.",
        )

    @staticmethod
    def _execute_tool(tool_name: str, tool_input: dict, tools: list) -> str:
        """Look up and execute a tool by name."""
        for t in tools:
            if t.name == tool_name:
                try:
                    return t.invoke(tool_input)
                except Exception as exc:
                    return f"Tool execution error: {exc}"
        return f"Unknown tool: {tool_name}"

    @staticmethod
    def _build_partial_result(
        request: InvestigationRequest,
        start_time: float,
        error: str = "",
    ) -> InvestigationResult:
        """Build a partial/failed investigation result."""
        return InvestigationResult(
            investigation_id=request.investigation_id,
            norad_cat_id=request.anomaly.norad_cat_id,
            satellite_name=request.satellite_name,
            orbit_regime=request.orbit_regime,
            anomaly_score=request.anomaly.composite_score,
            delta_v=request.anomaly.delta_v,
            insufficient_data=True,
            executive_summary=f"INSUFFICIENT DATA — Investigation incomplete. {error}",
            data_gaps=[error] if error else ["Investigation did not complete."],
            wall_clock_seconds=time.time() - start_time,
        )
