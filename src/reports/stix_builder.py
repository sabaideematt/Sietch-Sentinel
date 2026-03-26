"""STIX 2.1 bundle builder — Observed Data + Indicators + Sightings + Relationships."""

from __future__ import annotations

import logging
from datetime import datetime

from src.schemas import InvestigationResult

logger = logging.getLogger(__name__)


class STIXBundleBuilder:
    """Build STIX 2.1 bundles from investigation results."""

    def build(self, result: InvestigationResult):
        """
        Create a STIX 2.1 Bundle containing:
        - ObservedData for the anomaly
        - Indicator for each TTP match
        - Sighting linking observed data to indicators
        - Relationship objects tying everything together
        """
        from stix2 import (
            Bundle,
            ObservedData,
            Indicator,
            Sighting,
            Relationship,
            Identity,
            Note,
        )

        objects = []

        # Identity for Sietch Sentinel
        identity = Identity(
            name="Sietch Sentinel",
            identity_class="system",
            description="Autonomous satellite cyber-anomaly detection system",
        )
        objects.append(identity)

        # ObservedData for the anomaly
        observed = ObservedData(
            first_observed=result.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            last_observed=result.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            number_observed=1,
            object_refs=[identity.id],
            created_by_ref=identity.id,
            allow_custom=True,
            custom_properties={
                "x_sietch_norad_cat_id": result.norad_cat_id,
                "x_sietch_satellite_name": result.satellite_name,
                "x_sietch_orbit_regime": result.orbit_regime.value,
                "x_sietch_anomaly_score": result.anomaly_score,
                "x_sietch_investigation_id": result.investigation_id,
            },
        )
        objects.append(observed)

        # Indicators for each TTP match
        for ttp in result.ttp_matches:
            indicator = Indicator(
                name=f"[{ttp.framework}] {ttp.technique_id} — {ttp.technique_name}",
                description=ttp.evidence_summary,
                pattern=f"[x-sietch-ttp:technique_id = '{ttp.technique_id}']",
                pattern_type="stix",
                valid_from=result.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                created_by_ref=identity.id,
                confidence={"HIGH": 90, "MED": 60, "LOW": 30}.get(ttp.confidence.value, 30),
                allow_custom=True,
                custom_properties={
                    "x_sietch_framework": ttp.framework,
                    "x_sietch_technique_id": ttp.technique_id,
                    "x_sietch_natural_cause_ruled_out": ttp.natural_cause_ruled_out,
                },
            )
            objects.append(indicator)

            # Sighting linking observed data to indicator
            sighting = Sighting(
                sighting_of_ref=indicator.id,
                observed_data_refs=[observed.id],
                created_by_ref=identity.id,
            )
            objects.append(sighting)

            # Relationship
            rel = Relationship(
                source_ref=observed.id,
                target_ref=indicator.id,
                relationship_type="indicates",
                created_by_ref=identity.id,
            )
            objects.append(rel)

        # Note with executive summary
        if result.executive_summary:
            note = Note(
                content=result.executive_summary,
                object_refs=[observed.id],
                created_by_ref=identity.id,
            )
            objects.append(note)

        return Bundle(objects=objects, allow_custom=True)
