"""Sietch Sentinel CLI — main entry point for running the pipeline."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler

from src.config import settings

console = Console()


def _setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
def cli():
    """Sietch Sentinel — Agentic AI Satellite Cyber-Anomaly Detection."""
    _setup_logging()


@cli.command()
@click.argument("norad_id", type=int)
@click.option("--days", default=30, help="Days of TLE history to fetch")
def ingest(norad_id: int, days: int):
    """Fetch TLEs and compute delta-V estimates for a satellite."""
    from datetime import datetime, timedelta
    from src.ingestion import TLEFetcher, DeltaVCalculator

    fetcher = TLEFetcher()
    calculator = DeltaVCalculator()
    start = datetime.utcnow() - timedelta(days=days)

    async def _run():
        console.print(f"[bold blue]Fetching TLEs for NORAD {norad_id}...[/]")
        latest = await fetcher.fetch_latest_tle(norad_id)
        if latest:
            console.print(f"  Latest TLE: {latest.source}")
            console.print(f"  L1: {latest.line1}")
            console.print(f"  L2: {latest.line2}")

        history = await fetcher.fetch_tle_history(norad_id, start)
        console.print(f"  Historical TLEs: {len(history)} records")

        if len(history) >= 2:
            estimates = calculator.estimate_series(history)
            console.print(f"\n[bold green]Delta-V Estimates ({len(estimates)}):[/]")
            for est in estimates[:10]:
                console.print(
                    f"  {est.epoch_before:%Y-%m-%d} → {est.epoch_after:%Y-%m-%d}: "
                    f"Δv={est.delta_v_m_s:.2f} m/s ± {est.uncertainty_m_s:.2f}"
                )

    asyncio.run(_run())


@cli.command()
@click.argument("norad_id", type=int)
@click.option("--severity", default="mid", help="Force severity level (low/mid/high)")
def investigate(norad_id: int, severity: str):
    """Run a full investigation on a satellite anomaly."""
    from datetime import datetime
    from src.agent.orchestrator import Orchestrator
    from src.reports.generator import ReportGenerator
    from src.schemas import (
        AnomalyScore,
        AnomalySeverity,
        InvestigationRequest,
        OrbitRegime,
    )

    score = AnomalyScore(
        norad_cat_id=norad_id,
        timestamp=datetime.utcnow(),
        composite_score=0.75,
        severity=AnomalySeverity(severity),
    )
    request = InvestigationRequest(
        anomaly=score,
        orbit_regime=OrbitRegime.GEO,
    )

    orchestrator = Orchestrator()
    reporter = ReportGenerator()

    async def _run():
        console.print(f"[bold yellow]Investigating NORAD {norad_id} (severity: {severity})...[/]")
        result = await orchestrator.investigate(request)

        # Generate reports
        paths = reporter.save_reports(result)
        console.print(f"\n[bold green]Investigation Complete[/]")
        console.print(f"  ID: {result.investigation_id}")
        console.print(f"  Tool calls: {result.tool_calls_used}")
        console.print(f"  Wall clock: {result.wall_clock_seconds:.1f}s")
        console.print(f"  Insufficient data: {result.insufficient_data}")
        for fmt, path in paths.items():
            console.print(f"  Report ({fmt}): {path}")

        # Print NL brief
        console.print("\n" + reporter.to_nl_brief(result))

    asyncio.run(_run())


@cli.command()
@click.argument("norad_id", type=int)
def profile(norad_id: int):
    """Show the satellite profile from the Memory Layer."""
    from src.memory.store import MemoryStore

    store = MemoryStore()
    prof = store.get_satellite_profile(norad_id)
    if prof is None:
        console.print(f"[yellow]No profile found for NORAD {norad_id}.[/]")
        return

    console.print(f"[bold]Satellite Profile — NORAD {norad_id}[/]")
    console.print(f"  Name: {prof.object_name}")
    console.print(f"  Orbit: {prof.orbit_regime.value}")
    console.print(f"  Operator: {prof.operator or 'unknown'}")
    console.print(f"  Typical ΔV: {prof.typical_delta_v_m_s:.2f} m/s")
    console.print(f"  Maneuver freq: every {prof.maneuver_frequency_days:.1f} days")
    console.print(f"  Thresholds: [{prof.anomaly_threshold_low:.2f}, {prof.anomaly_threshold_high:.2f}]")
    console.print(f"  Investigations: {prof.total_investigations} (FP: {prof.false_positive_count})")


@cli.command()
def check_config():
    """Verify configuration and external service connectivity."""
    console.print("[bold]Sietch Sentinel — Configuration Check[/]\n")

    # Credentials
    console.print("[bold]Credentials:[/]")
    console.print(f"  Space-Track: {'✓' if settings.spacetrack_user else '✗ NOT SET'}")
    console.print(f"  Anthropic:   {'✓' if settings.anthropic_api_key else '✗ NOT SET'}")
    console.print(f"  Splunk HEC:  {'✓' if settings.splunk_hec_token else '– optional'}")
    console.print(f"  Elastic:     {'✓' if settings.elasticsearch_url else '– optional'}")

    # Directories
    console.print(f"\n[bold]Directories:[/]")
    console.print(f"  Project root: {settings.project_root}")
    console.print(f"  Data:         {settings.data_dir}")
    console.print(f"  Models:       {settings.models_dir}")
    console.print(f"  Logs:         {settings.logs_dir}")

    # Redis
    console.print(f"\n[bold]Services:[/]")
    from src.memory.store import MemoryStore
    store = MemoryStore()
    r = store._get_redis()
    console.print(f"  Redis: {'✓ connected' if r else '✗ unavailable (cache disabled)'}")

    console.print(f"\n[bold green]Config check complete.[/]")


if __name__ == "__main__":
    cli()
