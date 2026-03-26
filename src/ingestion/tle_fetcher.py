"""Fetch TLE data from Space-Track.org and CelesTrak."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from spacetrack import SpaceTrackClient

from src.config import settings
from src.schemas import TLERecord

logger = logging.getLogger(__name__)


class TLEFetcher:
    """Pull TLEs from Space-Track.org (primary) with CelesTrak fallback."""

    CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"

    def __init__(self):
        self._st_client: Optional[SpaceTrackClient] = None
        if settings.spacetrack_user and settings.spacetrack_pass:
            self._st_client = SpaceTrackClient(
                identity=settings.spacetrack_user,
                password=settings.spacetrack_pass,
            )
            logger.info("Space-Track client initialized.")
        else:
            logger.warning(
                "Space-Track credentials not set — using CelesTrak fallback only."
            )

    # ── Space-Track ──

    async def fetch_latest_tle(self, norad_id: int) -> Optional[TLERecord]:
        """Fetch the most recent TLE for a NORAD catalog ID."""
        if self._st_client is None:
            return await self._celestrak_latest(norad_id)
        try:
            data = self._st_client.tle_latest(
                norad_cat_id=norad_id, ordinal=1, format="tle"
            )
            if not data:
                logger.warning("No TLE returned from Space-Track for %s", norad_id)
                return await self._celestrak_latest(norad_id)
            return self._parse_spacetrack_tle(data, norad_id)
        except Exception as exc:
            logger.error("Space-Track fetch failed for %s: %s", norad_id, exc)
            return await self._celestrak_latest(norad_id)

    async def fetch_tle_history(
        self,
        norad_id: int,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> list[TLERecord]:
        """Fetch historical TLE series for delta-V analysis."""
        end = end or datetime.utcnow()
        if self._st_client is None:
            logger.warning("Historical TLE fetch requires Space-Track credentials.")
            return []
        try:
            date_range = f"{start:%Y-%m-%d}--{end:%Y-%m-%d}"
            data = self._st_client.tle(
                norad_cat_id=norad_id,
                epoch=date_range,
                orderby="epoch asc",
                format="tle",
            )
            return self._parse_tle_batch(data, norad_id)
        except Exception as exc:
            logger.error("Historical TLE fetch failed for %s: %s", norad_id, exc)
            return []

    # ── CelesTrak fallback ──

    async def _celestrak_latest(self, norad_id: int) -> Optional[TLERecord]:
        """Fetch latest GP data from CelesTrak as fallback."""
        url = f"{self.CELESTRAK_BASE}?CATNR={norad_id}&FORMAT=TLE"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                lines = resp.text.strip().splitlines()
                if len(lines) < 3:
                    return None
                return TLERecord(
                    norad_cat_id=norad_id,
                    object_name=lines[0].strip(),
                    epoch=datetime.utcnow(),  # refined during propagation
                    line1=lines[1].strip(),
                    line2=lines[2].strip(),
                    source="celestrak",
                )
        except Exception as exc:
            logger.error("CelesTrak fallback failed for %s: %s", norad_id, exc)
            return None

    # ── Parsing helpers ──

    @staticmethod
    def _parse_spacetrack_tle(raw: str, norad_id: int) -> Optional[TLERecord]:
        lines = raw.strip().splitlines()
        if len(lines) < 2:
            return None
        line1 = lines[0].strip() if lines[0].startswith("1") else lines[1].strip()
        line2 = lines[1].strip() if lines[1].startswith("2") else lines[0].strip()
        return TLERecord(
            norad_cat_id=norad_id,
            object_name=f"NORAD-{norad_id}",
            epoch=datetime.utcnow(),
            line1=line1,
            line2=line2,
            source="space-track",
        )

    @staticmethod
    def _parse_tle_batch(raw: str, norad_id: int) -> list[TLERecord]:
        records: list[TLERecord] = []
        lines = raw.strip().splitlines()
        i = 0
        while i + 1 < len(lines):
            l1 = lines[i].strip()
            l2 = lines[i + 1].strip()
            if l1.startswith("1") and l2.startswith("2"):
                records.append(
                    TLERecord(
                        norad_cat_id=norad_id,
                        object_name=f"NORAD-{norad_id}",
                        epoch=datetime.utcnow(),
                        line1=l1,
                        line2=l2,
                        source="space-track",
                    )
                )
                i += 2
            else:
                i += 1
        return records
