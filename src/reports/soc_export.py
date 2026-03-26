"""SOC integration — Splunk HEC, Elastic ECS, TAXII 2.1 export."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from src.config import settings
from src.schemas import InvestigationResult

logger = logging.getLogger(__name__)


class SOCExporter:
    """Export investigation results to SOC platforms."""

    # ── Splunk HEC ──

    @staticmethod
    async def export_to_splunk(result: InvestigationResult) -> bool:
        """Send investigation result to Splunk via HTTP Event Collector (HEC).
        Maps fields to Splunk CIM format."""
        if not settings.splunk_hec_url or not settings.splunk_hec_token:
            logger.warning("Splunk HEC not configured — skipping export.")
            return False

        # CIM-mapped event
        event = {
            "time": int(result.created_at.timestamp()),
            "sourcetype": "sietch:sentinel:investigation",
            "source": "sietch_sentinel",
            "event": {
                # CIM: Intrusion Detection
                "action": "allowed",
                "category": "satellite_anomaly",
                "severity": "high" if result.anomaly_score > 0.7 else "medium",
                # Custom fields
                "investigation_id": result.investigation_id,
                "norad_cat_id": result.norad_cat_id,
                "satellite_name": result.satellite_name,
                "orbit_regime": result.orbit_regime.value,
                "anomaly_score": result.anomaly_score,
                "executive_summary": result.executive_summary,
                "ttp_matches": [
                    {
                        "framework": t.framework,
                        "technique_id": t.technique_id,
                        "technique_name": t.technique_name,
                        "confidence": t.confidence.value,
                    }
                    for t in result.ttp_matches
                ],
                "evidence_chain": result.evidence_chain,
                "insufficient_data": result.insufficient_data,
                "tool_calls_used": result.tool_calls_used,
                "wall_clock_seconds": result.wall_clock_seconds,
            },
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.post(
                    f"{settings.splunk_hec_url}/services/collector/event",
                    headers={
                        "Authorization": f"Splunk {settings.splunk_hec_token}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(event),
                )
                resp.raise_for_status()
                logger.info("Exported to Splunk HEC: %s", result.investigation_id)
                return True
        except Exception as e:
            logger.error("Splunk HEC export failed: %s", e)
            return False

    # ── Elasticsearch ECS ──

    @staticmethod
    async def export_to_elastic(result: InvestigationResult) -> bool:
        """Send investigation result to Elasticsearch in ECS format."""
        if not settings.elasticsearch_url:
            logger.warning("Elasticsearch not configured — skipping export.")
            return False

        # ECS-mapped document
        doc = {
            "@timestamp": result.created_at.isoformat(),
            "event": {
                "kind": "alert",
                "category": ["intrusion_detection"],
                "type": ["info"],
                "module": "sietch_sentinel",
                "dataset": "sietch.investigation",
                "severity": int(result.anomaly_score * 100),
            },
            "threat": {
                "framework": "SPARTA+ATT&CK",
                "technique": [
                    {"id": t.technique_id, "name": t.technique_name}
                    for t in result.ttp_matches
                ],
            },
            "sietch": {
                "investigation_id": result.investigation_id,
                "norad_cat_id": result.norad_cat_id,
                "satellite_name": result.satellite_name,
                "orbit_regime": result.orbit_regime.value,
                "anomaly_score": result.anomaly_score,
                "executive_summary": result.executive_summary,
                "insufficient_data": result.insufficient_data,
            },
        }

        index = f"sietch-sentinel-{datetime.utcnow():%Y.%m}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.elasticsearch_url}/{index}/_doc",
                    headers={"Content-Type": "application/json"},
                    content=json.dumps(doc),
                )
                resp.raise_for_status()
                logger.info("Exported to Elasticsearch: %s", result.investigation_id)
                return True
        except Exception as e:
            logger.error("Elasticsearch export failed: %s", e)
            return False
